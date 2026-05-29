import warnings
warnings.filterwarnings('ignore')

import sys

import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

from xgboost import XGBClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import lightgbm as lgb

# ============================================================
# Техникийн үзүүлэлтүүд — цэвэр numpy/pandas (pandas_ta ХЭРЭГГҮЙ)
# ============================================================
def compute_indicators(df):
    close = df['close']
    high  = df['high']
    low   = df['low']

    df['SMA5']  = close.rolling(5).mean()
    df['SMA10'] = close.rolling(10).mean()
    df['SMA20'] = close.rolling(20).mean()

    def wma(s, n):
        weights = np.arange(1, n + 1)
        return s.rolling(n).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

    df['wma5']  = wma(close, 5)
    df['wma10'] = wma(close, 10)

    df['disparity5']  = close / df['SMA5']
    df['disparity10'] = close / df['SMA10']

    df['roc'] = close.pct_change(10) * 100

    # RSI
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))

    df['momentum'] = close - close.shift(10)
    df['std']      = close.rolling(5).std()

    # CCI
    tp        = (high + low + close) / 3
    df['cci'] = (tp - tp.rolling(20).mean()) / \
                (0.015 * tp.rolling(20).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True))

    # MACD
    ema12      = close.ewm(span=12, adjust=False).mean()
    ema26      = close.ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['ppo']  = (ema12 - ema26) / ema26 * 100

    # Stochastic
    lo14          = low.rolling(14).min()
    hi14          = high.rolling(14).max()
    df['stoch_k'] = (close - lo14) / (hi14 - lo14 + 1e-9) * 100
    df['stoch_d'] = df['stoch_k'].rolling(3).mean()

    # Bollinger Bands
    bb_mid        = close.rolling(20).mean()
    bb_std        = close.rolling(20).std()
    df['bb_upper']= bb_mid + 2 * bb_std
    df['bb_lower']= bb_mid - 2 * bb_std
    df['bb_pct']  = (close - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'] + 1e-9)

    return df.dropna()

# ============================================================
# Тикер оруулах
# ============================================================
print("\n" + "="*55)
print("  📈 БОДИТ ЦАГИЙН ХУВЬЦААНЫ ТААМАГЛАЛ")
print("="*55)
print("\nЖишээ тикерүүд:")
print("  AAPL    → Apple")
print("  TSLA    → Tesla")
print("  MSFT    → Microsoft")
print("  GOOGL   → Google")
print("  BTC-USD → Bitcoin")
print()

ticker = input("Хувьцааны тикер оруулна уу (жишээ: AAPL): ").strip().upper()
if not ticker:
    ticker = "AAPL"

# ============================================================
# Өгөгдөл татах
# ============================================================
print(f"\n⬇️  {ticker} өгөгдлийг татаж байна...")

end_date   = datetime.today()
start_date = end_date - timedelta(days=365 * 5)

stock = yf.Ticker(ticker)
df    = stock.history(start=start_date, end=end_date)

if df.empty:
    print(f"❌ '{ticker}' тикер олдсонгүй.")
    sys.exit(1)

df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
df.columns = ['open', 'high', 'low', 'close', 'volume']
df = df.dropna()

info          = stock.info
comp_name     = info.get('longName', ticker)
currency      = info.get('currency', 'USD')
current_price = df['close'].iloc[-1]
prev_price    = df['close'].iloc[-2]
change_pct    = (current_price - prev_price) / prev_price * 100

print(f"\n✅ {comp_name} ({ticker})")
print(f"   Одоогийн үнэ  : {current_price:,.2f} {currency}")
print(f"   Өчигдрөөс    : {change_pct:+.2f}%")
print(f"   Нийт өгөгдөл : {len(df)} өдөр")

# ============================================================
# Үзүүлэлт тооцоолох
# ============================================================
print("\n⚙️  Техникийн үзүүлэлт тооцоолж байна...")
df = compute_indicators(df)

feature_cols = ['SMA5', 'SMA10', 'SMA20', 'wma5', 'wma10',
                'disparity5', 'disparity10', 'roc', 'rsi',
                'momentum', 'std', 'cci', 'macd', 'ppo',
                'stoch_k', 'stoch_d', 'bb_pct']

df['target'] = np.where(df['close'].shift(-5) > df['close'], 1, 0)

latest_row = df.iloc[[-1]].copy()
X_predict = latest_row[feature_cols]

train_df = df.dropna(subset=feature_cols).iloc[:-5].copy()
X = df[feature_cols]
y = df['target']

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, shuffle=False)

# ============================================================
# Загварууд сургах
# ============================================================
print("🤖 Загварууд сургаж байна...")

rf = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
rf.fit(X_train, y_train)
rf_acc = accuracy_score(y_test, rf.predict(X_test))

xgb_clf = XGBClassifier(
    n_estimators=500, eta=0.1, max_depth=5,
    objective='binary:logistic', random_state=42,
    eval_metric='logloss', verbosity=0, device='cpu'
)
xgb_clf.fit(X_train, y_train)
xgb_acc = accuracy_score(y_test, xgb_clf.predict(X_test))

train_data = lgb.Dataset(X_train, label=y_train)
params = {
    'objective': 'binary', 'metric': 'binary_error',
    'num_leaves': 31, 'learning_rate': 0.1,
    'feature_fraction': 0.8, 'seed': 42, 'verbosity': -1
}
lgb_model = lgb.train(params, train_data, num_boost_round=200,
                      callbacks=[lgb.log_evaluation(period=-1)])
lgb_acc = accuracy_score(y_test,
    (lgb_model.predict(X_test) > 0.5).astype(int))

print(f"   Random Forest : {rf_acc:.1%}")
print(f"   XGBoost       : {xgb_acc:.1%}")
print(f"   LightGBM      : {lgb_acc:.1%}")

# ============================================================
# Таамаглал
# ============================================================
last_features = X.iloc[[-1]]
last_date     = df.index[-1]

rf_prob  = rf.predict_proba(last_features)[0][1]
xgb_prob = xgb_clf.predict_proba(last_features)[0][1]
lgb_prob = lgb_model.predict(last_features)[0]

total_acc     = rf_acc + xgb_acc + lgb_acc
weighted_prob = (rf_prob * rf_acc + xgb_prob * xgb_acc + lgb_prob * lgb_acc) / total_acc

results = [
    ("Random Forest", rf_prob,  rf_acc),
    ("XGBoost",       xgb_prob, xgb_acc),
    ("LightGBM",      lgb_prob, lgb_acc),
]

# ============================================================
# Үр дүн хэвлэх
# ============================================================
print("\n" + "="*55)
print(f"  🔮 ИРЭХ 5 ӨДРИЙН ТААМАГЛАЛ — {ticker}")
print("="*55)
print(f"  📅 Огноо        : {last_date.strftime('%Y-%m-%d')}")
print(f"  💰 Одоогийн үнэ : {current_price:,.2f} {currency}")
print(f"  📊 Өчигдрөөс   : {change_pct:+.2f}%")
print("-"*55)

for name, prob, acc in results:
    direction  = "📈 ӨСНӨ  " if prob >= 0.5 else "📉 БУУРНА"
    confidence = prob if prob >= 0.5 else 1 - prob
    bar        = "█" * int(confidence * 20)
    print(f"  {name:<15}: {direction} | {confidence:.1%} [{bar:<20}] acc:{acc:.0%}")

print("-"*55)
final_dir  = "📈 ӨСНӨ" if weighted_prob >= 0.5 else "📉 БУУРНА"
confidence = weighted_prob if weighted_prob >= 0.5 else 1 - weighted_prob
level      = "🟢 ӨНДӨР" if confidence >= 0.70 else ("🟡 ДУНД" if confidence >= 0.55 else "🔴 БАГА")

print(f"  🏆 НЭГТГЭСЭН       : {final_dir}")
print(f"     Итгэлийн түвшин : {confidence:.1%}")
print(f"     Итгэлийн зэрэг  : {level}")
print("="*55)

# ============================================================
# График
# ============================================================
fig, axes = plt.subplots(2, 2, figsize=(14, 9))
fig.suptitle(f"{comp_name} ({ticker}) — Таамаглалын дүн шинжилгээ",
             fontsize=14, fontweight='bold')

last60 = df.tail(60)

ax1 = axes[0, 0]
ax1.plot(last60.index, last60['close'],   color='steelblue', linewidth=2, label='Үнэ')
ax1.plot(last60.index, last60['SMA20'],  color='orange',    linewidth=1.2, linestyle='--', label='SMA20')
ax1.fill_between(last60.index, last60['bb_upper'], last60['bb_lower'],
                 alpha=0.1, color='gray', label='Bollinger')
ax1.set_title("Үнийн хөдөлгөөн (сүүлийн 60 өдөр)")
ax1.set_ylabel(f"Үнэ ({currency})")
ax1.legend(fontsize=8)
ax1.tick_params(axis='x', rotation=30)

ax2 = axes[0, 1]
ax2.plot(last60.index, last60['rsi'], color='purple', linewidth=1.5)
ax2.axhline(70, color='red',   linestyle='--', alpha=0.7, label='Хэт авсан (70)')
ax2.axhline(30, color='green', linestyle='--', alpha=0.7, label='Хэт худалдсан (30)')
ax2.fill_between(last60.index, last60['rsi'], 50,
                 where=last60['rsi'] >= 50, alpha=0.2, color='green')
ax2.fill_between(last60.index, last60['rsi'], 50,
                 where=last60['rsi'] < 50,  alpha=0.2, color='red')
ax2.set_title("RSI үзүүлэлт")
ax2.set_ylim(0, 100)
ax2.legend(fontsize=8)
ax2.tick_params(axis='x', rotation=30)

ax3   = axes[1, 0]
names = [r[0] for r in results] + ['Нэгтгэсэн']
probs = [r[1] for r in results] + [weighted_prob]
cols  = ['#2ecc71' if p >= 0.5 else '#e74c3c' for p in probs]
bars  = ax3.bar(names, probs, color=cols, alpha=0.85, edgecolor='white')
ax3.axhline(0.5, color='black', linestyle='--', alpha=0.5)
ax3.set_ylim(0, 1)
ax3.set_ylabel("Өсөх магадлал")
ax3.set_title("Загвар бүрийн таамаглал")
for bar, prob in zip(bars, probs):
    ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
             f'{prob:.1%}', ha='center', fontweight='bold', fontsize=10)

ax4 = axes[1, 1]
ax4.plot(last60.index, last60['macd'], color='blue', linewidth=1.5, label='MACD')
ax4.axhline(0, color='black', alpha=0.3)
ax4.fill_between(last60.index, last60['macd'], 0,
                 where=last60['macd'] >= 0, alpha=0.3, color='green', label='Эерэг')
ax4.fill_between(last60.index, last60['macd'], 0,
                 where=last60['macd'] < 0,  alpha=0.3, color='red',   label='Сөрөг')
ax4.set_title("MACD үзүүлэлт")
ax4.legend(fontsize=8)
ax4.tick_params(axis='x', rotation=30)

plt.tight_layout()
plt.savefig('prediction_result.png', dpi=150, bbox_inches='tight')
plt.show()

print(f"\n📊 График 'prediction_result.png' файлд хадгалагдлаа.")
print("\n⚠️  Анхааруулга: Энэ таамаглал зөвхөн судалгааны зорилготой.\n")