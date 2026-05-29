import warnings
warnings.filterwarnings('ignore')

import sys

import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, timezone

from xgboost import XGBClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import lightgbm as lgb

UTC_PLUS_3 = timezone(timedelta(hours=3))

# ============================================================
# Техникийн үзүүлэлтүүд
# ============================================================
def compute_indicators(df):
    close = df['close']
    high  = df['high']
    low   = df['low']

    df['SMA5']  = close.rolling(5).mean()
    df['SMA10'] = close.rolling(10).mean()
    df['SMA20'] = close.rolling(20).mean()

    def wma(s, n):
        w = np.arange(1, n + 1)
        return s.rolling(n).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)

    df['wma5']        = wma(close, 5)
    df['wma10']       = wma(close, 10)
    df['disparity5']  = close / df['SMA5']
    df['disparity10'] = close / df['SMA10']
    df['roc']         = close.pct_change(10) * 100

    delta     = close.diff()
    gain      = delta.clip(lower=0).rolling(14).mean()
    loss      = (-delta.clip(upper=0)).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))

    df['momentum'] = close - close.shift(10)
    df['std']      = close.rolling(5).std()

    tp        = (high + low + close) / 3
    df['cci'] = (tp - tp.rolling(20).mean()) / \
                (0.015 * tp.rolling(20).apply(
                    lambda x: np.mean(np.abs(x - x.mean())), raw=True))

    ema12      = close.ewm(span=12, adjust=False).mean()
    ema26      = close.ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['ppo']  = (ema12 - ema26) / ema26 * 100

    lo14          = low.rolling(14).min()
    hi14          = high.rolling(14).max()
    df['stoch_k'] = (close - lo14) / (hi14 - lo14 + 1e-9) * 100
    df['stoch_d'] = df['stoch_k'].rolling(3).mean()

    bb_mid         = close.rolling(20).mean()
    bb_std         = close.rolling(20).std()
    df['bb_upper'] = bb_mid + 2 * bb_std
    df['bb_lower'] = bb_mid - 2 * bb_std
    df['bb_pct']   = (close - df['bb_lower']) / \
                     (df['bb_upper'] - df['bb_lower'] + 1e-9)

    return df.dropna()

# ============================================================
# Тикер болон хугацаа сонгох
# ============================================================
print("\n" + "="*55)
print("  📈 ЦАГИЙН ХУВЬЦААНЫ ТААМАГЛАЛ (1ц эсвэл 4ц)")
print("="*55)
print("\nЖишээ тикерүүд:")
print("  AAPL    → Apple")
print("  TSLA    → Tesla")
print("  MSFT    → Microsoft")
print("  GOOGL   → Google")
print("  BTC-USD → Bitcoin")
print("  ETH-USD → Ethereum")
print()

ticker = input("Хувьцааны тикер оруулна уу (жишээ: AAPL): ").strip().upper()
if not ticker:
    ticker = "AAPL"

print("\nТаамаглалын хугацаа сонгоно уу:")
print("  1 → Дараагийн 1 цаг")
print("  4 → Дараагийн 4 цаг")
horizon_input = input("Сонголт (1 эсвэл 4): ").strip()
HORIZON = 4 if horizon_input == '4' else 1

print(f"\n⏰ Таамаглалын хугацаа: {HORIZON} цаг")

# ============================================================
# Өгөгдөл татах — 1h interval
# yfinance: 1h interval → max 730 хоног
# ============================================================
print(f"\n⬇️  {ticker} цагийн өгөгдлийг татаж байна...")

# 1h interval-д yfinance 60 хоногийн өгөгдөл л өгдөг
# Хангалттай өгөгдөл авахын тулд 59 хоног ашиглана
end_date   = datetime.now(UTC_PLUS_3)
start_date = end_date - timedelta(days=59)

df_raw = yf.download(
    ticker,
    start=start_date,
    end=end_date,
    interval='1h',
    progress=False,
    auto_adjust=True
)

if df_raw.empty:
    print(f"❌ '{ticker}' өгөгдөл татагдсангүй. Тикерээ шалгана уу.")
    sys.exit(1)

# MultiIndex баганыг хавтгайруулах
if isinstance(df_raw.columns, pd.MultiIndex):
    df_raw.columns = df_raw.columns.get_level_values(0)

df_raw = df_raw[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
df_raw.columns = ['open', 'high', 'low', 'close', 'volume']
df_raw = df_raw.dropna()

# UTC+3 timezone болгох
if isinstance(df_raw.index, pd.DatetimeIndex):

    # timezone байхгүй бол UTC гэж үзнэ
    if df_raw.index.tz is None:
        df_raw.index = df_raw.index.tz_localize('UTC')

    # UTC+3 руу хөрвүүлэх
    df_raw.index = df_raw.index.tz_convert(UTC_PLUS_3)

    # timezone мэдээллийг хадгалалгүй цэвэр datetime болгох
    df_raw.index = df_raw.index.tz_localize(None)

stock     = yf.Ticker(ticker)
info      = stock.info
comp_name = info.get('longName', ticker)
currency  = info.get('currency', 'USD')

live_price = (
    info.get('currentPrice')
    or info.get('regularMarketPrice')
    or info.get('ask')
    or info.get('bid')
)

# UTC+3 одоогийн цаг
now_realtime = datetime.now(UTC_PLUS_3)

# realtime candle нэмэх
if live_price is not None:
    latest_time = df_raw.index[-1]

    # timezoneгүй datetime болгох
    latest_time = latest_time.replace(tzinfo=None)
    now_clean   = now_realtime.replace(
        minute=0,
        second=0,
        microsecond=0,
        tzinfo=None
    )

    # хамгийн сүүлийн candle хуучин бол realtime мөр нэмнэ
    if latest_time < now_clean:

        live_row = pd.DataFrame({
            'open': df_raw['close'].iloc[-1],
            'high': max(df_raw['close'].iloc[-1], live_price),
            'low':  min(df_raw['close'].iloc[-1], live_price),
            'close': live_price,
            'volume': 0
        }, index=[now_clean])

        df_raw = pd.concat([df_raw, live_row])

        # duplicate цаг устгах
        df_raw = df_raw[~df_raw.index.duplicated(keep='last')]

# одоогийн үнэ
current_price = float(df_raw['close'].iloc[-1])
prev_price    = float(df_raw['close'].iloc[-2])

change_pct = (current_price - prev_price) / prev_price * 100

current_time = df_raw.index[-1]

prev_price    = float(df_raw['close'].iloc[-2])
change_pct    = (current_price - prev_price) / prev_price * 100
current_time  = df_raw.index[-1]

print(f"\n✅ {comp_name} ({ticker})")
print(f"   Сүүлийн цаг   : {current_time.strftime('%Y-%m-%d %H:%M')}")
print(f"   Одоогийн үнэ  : {current_price:,.2f} {currency}")
print(f"   Өмнөх цагаас  : {change_pct:+.2f}%")
print(f"   Нийт өгөгдөл  : {len(df_raw)} цагийн мөр")

if len(df_raw) < 100:
    print("⚠️  Өгөгдөл хэт цөөн байна. Крипто эсвэл том тикер ашиглана уу.")

# ============================================================
# Техникийн үзүүлэлт
# ============================================================
print("\n⚙️  Техникийн үзүүлэлт тооцоолж байна...")
df = compute_indicators(df_raw.copy())
df['target'] = (df['close'].shift(-HORIZON) > df['close']).astype(int)

feature_cols = ['SMA5', 'SMA10', 'SMA20', 'wma5', 'wma10',
                'disparity5', 'disparity10', 'roc', 'rsi',
                'momentum', 'std', 'cci', 'macd', 'ppo',
                'stoch_k', 'stoch_d', 'bb_pct']

# ============================================================
# Таамаглалын input — HORIZON цагийн өмнөх мөр
# Тэр мөрөөр "HORIZON цагийн дараа өснө үү?" гэж таамаглана
# Хариулт нь = одоогийн үнэтэй харьцуулна
# ============================================================
target_time  = df.index[-1]

# яг HORIZON цагийн өмнөх цаг
desired_time = target_time - timedelta(hours=HORIZON)

# хамгийн ойрын өмнөх мөр олох
past_df = df[df.index <= desired_time]

if len(past_df) == 0:
    print("❌ HORIZON хугацааны өмнөх өгөгдөл олдсонгүй.")
    sys.exit(1)

input_time  = past_df.index[-1]
input_row   = past_df[feature_cols].iloc[-1]
input_price = float(past_df['close'].iloc[-1])
actual_price = float(df['close'].iloc[-1])
price_change   = (actual_price - input_price) / input_price * 100
real_dir       = "📈 ӨССӨН" if actual_price > input_price else "📉 БУУРСАН"

print(f"\n   Input цаг     : {input_time.strftime('%Y-%m-%d %H:%M')}  ← {HORIZON}ц өмнө")
print(f"   Input үнэ     : {input_price:,.2f} {currency}")
print(f"   Одоогийн цаг  : {target_time.strftime('%Y-%m-%d %H:%M')}  ← одоо")
print(f"   Одоогийн үнэ  : {actual_price:,.2f} {currency}")
print(f"   Бодит өөрчлөлт: {price_change:+.2f}%  {real_dir}")

# ============================================================
# Загвар сургах
# target: HORIZON цагийн дараа үнэ өсөх эсэх
# ============================================================
now_time   = df.index[-1]
now_price  = float(df['close'].iloc[-1])

# яг HORIZON цагийн өмнөх хугацаа
desired_time = now_time - timedelta(hours=HORIZON)

# desired_time-ээс өмнөх хамгийн сүүлийн мөр
past_df = df[df.index <= desired_time]

if len(past_df) == 0:
    print(f"❌ {HORIZON} цагийн өмнөх өгөгдөл олдсонгүй.")
    sys.exit(1)

past_time  = past_df.index[-1]
past_price = float(past_df['close'].iloc[-1])

# тухайн үеийн feature row
predict_row = past_df[feature_cols].iloc[[-1]]



# Сүүлийн HORIZON мөрийг хасна (target байхгүй)
df_train = df.dropna(subset=feature_cols + ['target']).copy()
df_train = df_train.iloc[:-HORIZON].copy()
if len(df_train) < 50:
    print("❌ Өгөгдөл хэт цөөн. Загвар сургах боломжгүй.")
    sys.exit(1)

X = df_train[feature_cols]
y = df_train['target']

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, shuffle=False)

print(f"\n🤖 Загварууд сургаж байна... ({len(df_train)} мөр)")

rf = RandomForestClassifier(
    n_estimators=300, random_state=42, n_jobs=-1,
    max_depth=6, min_samples_leaf=5, max_features='sqrt'
)
rf.fit(X_train, y_train)
rf_acc = accuracy_score(y_test, rf.predict(X_test))

xgb_clf = XGBClassifier(
    n_estimators=500, eta=0.05, max_depth=4,
    subsample=0.8, colsample_bytree=0.8,
    min_child_weight=5,
    objective='binary:logistic', random_state=42,
    eval_metric='logloss', verbosity=0, device='cpu'
)
xgb_clf.fit(X_train, y_train,
            eval_set=[(X_test, y_test)], verbose=False)
xgb_acc = accuracy_score(y_test, xgb_clf.predict(X_test))

train_data = lgb.Dataset(X_train, label=y_train)
params = {
    'objective': 'binary', 'metric': 'binary_error',
    'num_leaves': 15, 'learning_rate': 0.05,
    'feature_fraction': 0.7, 'bagging_fraction': 0.8,
    'bagging_freq': 5, 'min_data_in_leaf': 5,
    'seed': 42, 'verbosity': -1
}
lgb_model = lgb.train(params, train_data, num_boost_round=300,
                      callbacks=[lgb.log_evaluation(period=-1)])
lgb_acc = accuracy_score(y_test,
    (lgb_model.predict(X_test) > 0.5).astype(int))

print(f"   Random Forest : {rf_acc:.1%}")
print(f"   XGBoost       : {xgb_acc:.1%}")
print(f"   LightGBM      : {lgb_acc:.1%}")

# ============================================================
# ТААМАГЛАЛ ГАРГАХ
# ============================================================
predict_input = pd.DataFrame([input_row], columns=feature_cols)

rf_prob  = rf.predict_proba(predict_input)[0][1]
xgb_prob = xgb_clf.predict_proba(predict_input)[0][1]
lgb_prob = lgb_model.predict(predict_input)[0]

# acc >= 54% загваруудыг нэгтгэнэ
MIN_ACC    = 0.54
candidates = [(rf_prob, rf_acc), (xgb_prob, xgb_acc), (lgb_prob, lgb_acc)]
good       = [(p, a) for p, a in candidates if a >= MIN_ACC]

if good:
    total_w       = sum(a for _, a in good)
    weighted_prob = sum(p * a for p, a in good) / total_w
    used_count    = len(good)
else:
    best_p, best_a = max(candidates, key=lambda x: x[1])
    weighted_prob  = best_p
    used_count     = 1

results = [
    ("Random Forest", rf_prob,  rf_acc),
    ("XGBoost",       xgb_prob, xgb_acc),
    ("LightGBM",      lgb_prob, lgb_acc),
]

# ============================================================
# ҮР ДҮН
# ============================================================
predict_until = target_time.replace(tzinfo= UTC_PLUS_3) + timedelta(hours=HORIZON)

print("\n" + "="*62)
print(f"  🔮 ДАРААГИЙН {HORIZON} ЦАГИЙН ТААМАГЛАЛ — {ticker}")
print("="*62)
print(f"  📅 Input цаг         : {input_time.strftime('%Y-%m-%d %H:%M')}  ← {HORIZON}ц өмнө")
print(f"  💰 Input үнэ         : {input_price:,.4f} {currency}")
print(f"  📅 Одоогийн цаг      : {target_time.strftime('%Y-%m-%d %H:%M')}  ← одоо")
print(f"  💰 Одоогийн үнэ     : {actual_price:,.4f} {currency}")
print(f"  📊 Бодит өөрчлөлт   : {price_change:+.2f}%  {real_dir}")
print(f"  🎯 Таамаглал хүртэл  : {predict_until.strftime('%Y-%m-%d %H:%M')}")
print("-"*62)

for name, prob, acc in results:
    flag      = "✓" if acc >= MIN_ACC else "✗"
    direction = "📈 ӨСНӨ  " if prob >= 0.5 else "📉 БУУРНА"
    conf      = prob if prob >= 0.5 else 1 - prob
    bar       = "█" * int(conf * 20)
    print(f"  {flag} {name:<15}: {direction} | {conf:.1%} [{bar:<20}] acc:{acc:.0%}")

print("-"*62)
final_dir  = "📈 ӨСНӨ" if weighted_prob >= 0.5 else "📉 БУУРНА"
confidence = weighted_prob if weighted_prob >= 0.5 else 1 - weighted_prob
level      = "🟢 ӨНДӨР" if confidence >= 0.70 else \
             ("🟡 ДУНД" if confidence >= 0.55 else "🔴 БАГА")

print(f"  🏆 НЭГТГЭСЭН        : {final_dir}")
print(f"     Итгэлийн түвшин  : {confidence:.1%}")
print(f"     Итгэлийн зэрэг   : {level}")
print(f"     Ашигласан загвар : {used_count}/3")
print("-"*62)

predicted_up = weighted_prob >= 0.5
actual_up    = actual_price > input_price
correct      = predicted_up == actual_up
print(f"  🎯 {HORIZON}ц өмнөх таамаглал зөв эсэх: "
      f"{'✅ ЗӨВТ' if correct else '❌ БУРУУ'}")
print("="*62)

# ============================================================
# ГРАФИК
# ============================================================
last_n = min(48, len(df))   # сүүлийн 48 цаг (2 хоног)
last48 = df.tail(last_n)

fig, axes = plt.subplots(2, 2, figsize=(14, 9))
fig.suptitle(
    f"{comp_name} ({ticker}) — {HORIZON} цагийн таамаглал  |  "
    f"Одоо: {actual_price:,.2f} {currency}",
    fontsize=13, fontweight='bold')

# 1. Үнэ + Bollinger
ax1 = axes[0, 0]
ax1.plot(last48.index, last48['close'],   color='steelblue', lw=2,   label='Үнэ')
ax1.plot(last48.index, last48['SMA20'],  color='orange',    lw=1.2, ls='--', label='SMA20')
ax1.fill_between(last48.index, last48['bb_upper'], last48['bb_lower'],
                 alpha=0.1, color='gray', label='Bollinger')
ax1.axvline(input_time,  color='blue',  ls='--', lw=1.2, alpha=0.8,
            label=f'Input ({input_time.strftime("%m/%d %H:%M")})')
ax1.axvline(target_time, color='green', ls='--', lw=1.2, alpha=0.8,
            label=f'Одоо ({target_time.strftime("%m/%d %H:%M")})')
color_arrow = 'green' if weighted_prob >= 0.5 else 'red'
ax1.annotate(
    f'{"▲" if weighted_prob >= 0.5 else "▼"} {confidence:.0%}',
    xy=(target_time, actual_price),
    xytext=(target_time, actual_price * (1.005 if weighted_prob >= 0.5 else 0.995)),
    color=color_arrow, fontsize=13, fontweight='bold', ha='center'
)
ax1.set_title(f"Үнийн хөдөлгөөн (сүүлийн {last_n} цаг)")
ax1.set_ylabel(f"Үнэ ({currency})")
ax1.legend(fontsize=7)
ax1.tick_params(axis='x', rotation=30)

# 2. RSI
ax2 = axes[0, 1]
ax2.plot(last48.index, last48['rsi'], color='purple', lw=1.5)
ax2.axhline(70, color='red',   ls='--', alpha=0.7, label='Хэт авсан (70)')
ax2.axhline(30, color='green', ls='--', alpha=0.7, label='Хэт худалдсан (30)')
ax2.fill_between(last48.index, last48['rsi'], 50,
                 where=last48['rsi'] >= 50, alpha=0.2, color='green')
ax2.fill_between(last48.index, last48['rsi'], 50,
                 where=last48['rsi'] <  50, alpha=0.2, color='red')
ax2.axvline(target_time, color='green', ls='--', lw=1, alpha=0.6)
ax2.set_title("RSI үзүүлэлт")
ax2.set_ylim(0, 100)
ax2.legend(fontsize=7)
ax2.tick_params(axis='x', rotation=30)

# 3. Загваруудын магадлал
ax3   = axes[1, 0]
names = [r[0] for r in results] + ['Нэгтгэсэн']
probs = [r[1] for r in results] + [weighted_prob]
cols  = ['#2ecc71' if p >= 0.5 else '#e74c3c' for p in probs]
bars  = ax3.bar(names, probs, color=cols, alpha=0.85, edgecolor='white', width=0.5)
ax3.axhline(0.5, color='black', ls='--', alpha=0.5, label='Босго (0.5)')
ax3.set_ylim(0, 1.1)
ax3.set_ylabel("Өсөх магадлал")
ax3.set_title(f"Загвар бүрийн таамаглал ({HORIZON}ц)")
for bar, prob in zip(bars, probs):
    ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
             f'{prob:.1%}', ha='center', fontweight='bold', fontsize=10)
ax3.legend(fontsize=8)

# 4. MACD
ax4 = axes[1, 1]
ax4.plot(last48.index, last48['macd'], color='blue', lw=1.5, label='MACD')
ax4.axhline(0, color='black', alpha=0.3)
ax4.fill_between(last48.index, last48['macd'], 0,
                 where=last48['macd'] >= 0, alpha=0.3, color='green', label='Эерэг')
ax4.fill_between(last48.index, last48['macd'], 0,
                 where=last48['macd'] <  0, alpha=0.3, color='red',   label='Сөрөг')
ax4.axvline(target_time, color='green', ls='--', lw=1, alpha=0.6)
ax4.set_title("MACD үзүүлэлт")
ax4.legend(fontsize=7)
ax4.tick_params(axis='x', rotation=30)

plt.tight_layout()
plt.savefig('prediction_result.png', dpi=150, bbox_inches='tight')
plt.show()

print(f"\n📊 График 'prediction_result.png' файлд хадгалагдлаа.")
print("⚠️  Анхааруулга: Энэ таамаглал зөвхөн судалгааны зорилготой.\n")