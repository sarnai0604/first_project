import os
import io
import zipfile
import urllib.request
import warnings
os.environ["OMP_NUM_THREADS"] = "4"
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
def out(name):
    return os.path.join(OUTPUT_DIR, name)

plt.rcParams.update({
    "figure.facecolor": "#0f0f1a",
    "axes.facecolor": "#161625",
    "axes.edgecolor": "#2a2a45",
    "axes.labelcolor": "#c8c8e0",
    "xtick.color": "#8888aa",
    "ytick.color": "#8888aa",
    "text.color": "#e0e0f0",
    "grid.color": "#2a2a45",
    "grid.linewidth": 0.6,
    "font.family": "DejaVu Sans",
    "font.size": 11,
})
PALETTE = ["#7b5cfa", "#fa5c7b", "#5cfabd", "#fac85c"]

# ─────────────────────────────────────────────────────────
# 1. MovieLens 1M ТАТАЖ АВАХ
# ─────────────────────────────────────────────────────────
DATA_DIR = os.path.join(OUTPUT_DIR, "ml-1m")
ZIP_URL  = "https://files.grouplens.org/datasets/movielens/ml-1m.zip"
ZIP_PATH = os.path.join(OUTPUT_DIR, "ml-1m.zip")

if not os.path.exists(DATA_DIR):
    print("⬇  MovieLens 1M татаж байна (~6MB)...")
    urllib.request.urlretrieve(ZIP_URL, ZIP_PATH)
    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        z.extractall(OUTPUT_DIR)
    os.remove(ZIP_PATH)
    print("✓  Татаж дуусав!")
else:
    print("✓  Өгөгдөл аль хэдийн байна, дахин татахгүй.")

# ─────────────────────────────────────────────────────────
# 2. ӨГӨГДӨЛ УНШИЖ ЦЭВЭРЛЭХ
# ─────────────────────────────────────────────────────────
users = pd.read_csv(
    os.path.join(DATA_DIR, "users.dat"),
    sep="::", engine="python",
    names=["UserID","Gender","Age","Occupation","Zip"],
    encoding="latin-1"
)

ratings = pd.read_csv(
    os.path.join(DATA_DIR, "ratings.dat"),
    sep="::", engine="python",
    names=["UserID","MovieID","Rating","Timestamp"],
    encoding="latin-1"
)

movies = pd.read_csv(
    os.path.join(DATA_DIR, "movies.dat"),
    sep="::", engine="python",
    names=["MovieID","Title","Genres"],
    encoding="latin-1"
)

print(f"\n📊 Хэрэглэгч: {len(users):,}  |  Үнэлгээ: {len(ratings):,}  |  Кино: {len(movies):,}")

# ─────────────────────────────────────────────────────────
# 3. FEATURE ENGINEERING — ШИНЭ ҮЗҮҮЛЭЛТҮҮД
# ─────────────────────────────────────────────────────────
print("\nШинэ үзүүлэлтүүдийг тооцоолж байна...")

# А. Долоо хоногт үздэг цаг (Timestamp ашиглан долоо хоногийн дундаж киног олоод 2 цагаар үржүүлнэ)
ratings['Date'] = pd.to_datetime(ratings['Timestamp'], unit='s')
ratings['YearWeek'] = ratings['Date'].dt.to_period('W')
weekly_counts = ratings.groupby(['UserID', 'YearWeek']).size().reset_index(name='Count')
user_weekly_avg = weekly_counts.groupby('UserID')['Count'].mean().reset_index(name='AvgMoviesPerWeek')
user_weekly_avg['WeeklyHours'] = user_weekly_avg['AvgMoviesPerWeek'] * 2

# Б. Дундаж үнэлгээ
user_stats = ratings.groupby("UserID").agg(AvgRating=("Rating", "mean")).reset_index()

# В. Дуртай ТОП 3 жанр олох
ratings_movies = ratings.merge(movies[["MovieID","Genres"]], on="MovieID")
ratings_movies["PrimaryGenre"] = ratings_movies["Genres"].str.split("|").str[0]

genre_counts = ratings_movies.groupby(["UserID", "PrimaryGenre"]).size().reset_index(name="GenreCount")
genre_counts = genre_counts.sort_values(["UserID", "GenreCount"], ascending=[True, False])
genre_counts["Rank"] = genre_counts.groupby("UserID").cumcount() + 1

top_3_genres = genre_counts[genre_counts["Rank"] <= 3].pivot(index="UserID", columns="Rank", values="PrimaryGenre").reset_index()
top_3_genres.columns = ["UserID", "TopGenre_1", "TopGenre_2", "TopGenre_3"]
top_3_genres = top_3_genres.fillna("None")

# Г. Бүх өгөгдлийг нэгтгэх
df = users[["UserID", "Age"]].merge(user_weekly_avg[["UserID", "WeeklyHours"]], on="UserID")
df = df.merge(user_stats, on="UserID")
df = df.merge(top_3_genres, on="UserID")

# Д. Жанруудыг кодолж тоонд шилжүүлэх
le = LabelEncoder()
all_genres = pd.concat([df["TopGenre_1"], df["TopGenre_2"], df["TopGenre_3"]]).unique()
le.fit(all_genres)
df["GenreCode_1"] = le.transform(df["TopGenre_1"])
df["GenreCode_2"] = le.transform(df["TopGenre_2"])
df["GenreCode_3"] = le.transform(df["TopGenre_3"])

print(f"✓  Feature engineering дуусав. Нийт хэрэглэгч: {len(df):,}")
print(df[["Age","WeeklyHours","AvgRating"]].describe().round(2))

# ─────────────────────────────────────────────────────────
# 4. SCALING + ELBOW + SILHOUETTE
# ─────────────────────────────────────────────────────────
features = ["Age", "WeeklyHours", "AvgRating", "GenreCode_1", "GenreCode_2", "GenreCode_3"]
scaler   = StandardScaler()
X        = scaler.fit_transform(df[features])

inertias, silhouettes = [], []
K_range = range(2, 8)
print("\nElbow + Silhouette тооцоолж байна...")
for k in K_range:
    km   = KMeans(n_clusters=k, random_state=42, n_init=10)
    labs = km.fit_predict(X)
    inertias.append(km.inertia_)
    silhouettes.append(silhouette_score(X, labs, sample_size=3000, random_state=42))
    print(f"  K={k}  inertia={km.inertia_:,.0f}  silhouette={silhouettes[-1]:.3f}")

fig, axes = plt.subplots(1, 2, figsize=(14, 4))
fig.suptitle("Оновчтой K тодорхойлох — Шинэ үзүүлэлтүүдээр", fontsize=13, fontweight="bold")

axes[0].plot(K_range, inertias, "o-", color=PALETTE[0], linewidth=2, markersize=7)
axes[0].axvline(4, color=PALETTE[1], ls="--", alpha=0.7, label="K=4")
axes[0].set(xlabel="K", ylabel="Inertia", title="Elbow Method")
axes[0].legend(); axes[0].grid(True)

axes[1].plot(K_range, silhouettes, "s-", color=PALETTE[2], linewidth=2, markersize=7)
axes[1].axvline(4, color=PALETTE[1], ls="--", alpha=0.7, label="K=4")
axes[1].set(xlabel="K", ylabel="Silhouette Score", title="Silhouette Score")
axes[1].legend(); axes[1].grid(True)

plt.tight_layout()
plt.savefig(out("01_elbow_silhouette.png"), dpi=150, bbox_inches="tight")
plt.show()

# ─────────────────────────────────────────────────────────
# 5. K-MEANS СУРГАЛТ  (K=4)
# ─────────────────────────────────────────────────────────
K = 4
km_final = KMeans(n_clusters=K, random_state=42, n_init=10)
df["Cluster"] = km_final.fit_predict(X)

# Долоо хоногт үздэг цагийн дунджаар эрэмбэлж нэрлэх
order = df.groupby("Cluster")["WeeklyHours"].mean().sort_values(ascending=False).index.tolist()
remap = {old: new for new, old in enumerate(order)}
df["Cluster"] = df["Cluster"].map(remap)

CLUSTER_LABELS = [
    "Кинонд донтсон идэвхтэй үзэгч", 
    "Дундаж идэвхтэй насанд хүрэгчид",
    "Амралтын өдрөөр бага зэрэг үздэг", 
    "Хааяа нэг үздэг чанга шүүмжлэгч"
]

df["ClusterName"] = df["Cluster"].map({i: CLUSTER_LABELS[i] for i in range(K)})
print(f"\n✓  K-Means дуусав. Silhouette: {silhouette_score(X, df['Cluster'], sample_size=3000, random_state=42):.3f}")

# ─────────────────────────────────────────────────────────
# 6. PCA 2D SCATTER
# ─────────────────────────────────────────────────────────
pca   = PCA(n_components=2, random_state=42)
X_pca = pca.fit_transform(X)
df["PCA1"] = X_pca[:, 0]
df["PCA2"] = X_pca[:, 1]

fig, ax = plt.subplots(figsize=(11, 7))
for c in range(K):
    m = df["Cluster"] == c
    ax.scatter(df.loc[m,"PCA1"], df.loc[m,"PCA2"],
               color=PALETTE[c], alpha=0.4, s=20, label=CLUSTER_LABELS[c])

centers_pca = pca.transform(km_final.cluster_centers_[[order.index(i) for i in range(K)]])
ax.scatter(centers_pca[:,0], centers_pca[:,1],
           s=250, marker="*", color="white", edgecolors="black", linewidth=0.8,
           zorder=5, label="Кластерийн төв")

var = pca.explained_variance_ratio_
ax.set_xlabel(f"PCA 1  ({var[0]*100:.1f}%)", fontsize=11)
ax.set_ylabel(f"PCA 2  ({var[1]*100:.1f}%)", fontsize=11)
ax.set_title(f"K-Means кластер — Шинэ үзүүлэлтүүдийн PCA 2D проекц", fontsize=13, fontweight="bold")
ax.legend(framealpha=0.2, fontsize=10)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(out("02_pca_scatter.png"), dpi=150, bbox_inches="tight")
plt.show()

# ─────────────────────────────────────────────────────────
# 7. RADAR CHART
# ─────────────────────────────────────────────────────────
radar_features = ["Age","WeeklyHours","AvgRating"]
radar_labels   = ["Нас","Үздэг цаг (Долоо хоног)","Дундаж үнэлгээ"]
summary = df.groupby("Cluster")[radar_features].mean()
norm    = (summary - summary.min()) / (summary.max() - summary.min())

angles  = np.linspace(0, 2*np.pi, len(radar_features), endpoint=False).tolist()
angles += angles[:1]

fig, axes = plt.subplots(2, 2, figsize=(12, 10), subplot_kw=dict(polar=True))
fig.suptitle("Кластер бүрийн шинэчилсэн профайл", fontsize=14, fontweight="bold", y=1.01)

for i, ax in enumerate(axes.flat):
    vals = norm.loc[i].tolist() + norm.loc[i].tolist()[:1]
    ax.plot(angles, vals, color=PALETTE[i], linewidth=2.5)
    ax.fill(angles, vals, color=PALETTE[i], alpha=0.25)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(radar_labels, fontsize=10)
    ax.set_yticklabels([])
    ax.set_title(CLUSTER_LABELS[i], color=PALETTE[i], fontsize=12, fontweight="bold", pad=15)
    ax.grid(color="#2a2a45")
    raw = summary.loc[i]
    
    # Режимийн дагуу хамгийн дуртай 1 дэх жанрыг олно
    sub_cluster = df[df["Cluster"]==i]
    top_1_g = sub_cluster["TopGenre_1"].mode()[0]
    
    ax.annotate(
        f"Нас: {raw['Age']:.1f} | Үздэг цаг: {raw['WeeklyHours']:.1f}ц\nДундаж үнэлгээ: {raw['AvgRating']:.2f}\nТоп Жанр: {top_1_g}",
        xy=(0.5,-0.25), xycoords="axes fraction", ha="center", fontsize=9, color="#9090b0"
    )

plt.tight_layout()
plt.savefig(out("03_radar_profiles.png"), dpi=150, bbox_inches="tight")
plt.show()

# ─────────────────────────────────────────────────────────
# 8. ТОП 1 ЖАНРЫН ХУВААРИЛАЛТ (STACKED BAR)
# ─────────────────────────────────────────────────────────
genre_cluster = (
    df.groupby(["Cluster","TopGenre_1"])
      .size().unstack(fill_value=0)
      .div(df.groupby("Cluster").size(), axis=0)
)
top_genres_list = genre_cluster.sum().sort_values(ascending=False).head(6).index.tolist()
other = genre_cluster.drop(columns=top_genres_list, errors="ignore").sum(axis=1)
genre_cluster = genre_cluster[top_genres_list].copy()
genre_cluster["Бусад"] = other

fig, ax = plt.subplots(figsize=(12, 6))
colors  = plt.cm.tab10(np.linspace(0, 1, len(genre_cluster.columns)))
bottom  = np.zeros(K)

for i, genre in enumerate(genre_cluster.columns):
    vals = genre_cluster[genre].values
    ax.bar(range(K), vals, bottom=bottom, color=colors[i], label=genre, width=0.6)
    for j,(v,b) in enumerate(zip(vals,bottom)):
        if v > 0.05:
            ax.text(j, b+v/2, genre[:5], ha="center", va="center", fontsize=8, color="white", fontweight="bold")
    bottom += vals

ax.set_xticks(range(K))
ax.set_xticklabels([f"Бүлэг {i}\n{CLUSTER_LABELS[i]}" for i in range(K)], fontsize=10)
ax.set_ylabel("Эзлэх хувь")
ax.set_title("Кластер бүрийн Нэгдүгээр дуртай жанрын хуваарилалт", fontsize=13, fontweight="bold")
ax.legend(loc="upper right", bbox_to_anchor=(1.18,1), fontsize=9, framealpha=0.15)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x,_: f"{x:.0%}"))
ax.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig(out("04_genre_distribution.png"), dpi=150, bbox_inches="tight")
plt.show()

# ─────────────────────────────────────────────────────────
# 9. ШИНЭЧИЛСЭН ДҮГНЭЛТ
# ─────────────────────────────────────────────────────────
print("\n" + "═"*65)
print("  КЛАСТЕРИЙН ШИНЭЧИЛСЭН ДҮГНЭЛТ (Шинэ Үзүүлэлтүүдээр)")
print("═"*65)
for c in range(K):
    sub = df[df["Cluster"]==c]
    print(f"\n🎬  Бүлэг {c} — {CLUSTER_LABELS[c]}  (n={len(sub):,})")
    print(f"   Дундаж нас             : {sub['Age'].mean():.1f} нас")
    print(f"   Долоо хоногт үздэг цаг : {sub['WeeklyHours'].mean():.1f} цаг")
    print(f"   Дундаж үнэлгээ         : {sub['AvgRating'].mean():.2f} / 5")
    print(f"   Дуртай ТОП 3 Жанр      : 1. {sub['TopGenre_1'].mode()[0]} | 2. {sub['TopGenre_2'].mode()[0]} | 3. {sub['TopGenre_3'].mode()[0]}")

print(f"\n✅  Бүх шинэчилсэн зургууд '{OUTPUT_DIR}' хавтаст амжилттай хадгалагдлаа.")