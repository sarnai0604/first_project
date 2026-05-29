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
# Хэрэглэгчид: UserID::Gender::Age::Occupation::Zip (Gender-ийг унших боловч ашиглахгүй)
users = pd.read_csv(
    os.path.join(DATA_DIR, "users.dat"),
    sep="::", engine="python",
    names=["UserID","Gender","Age","Occupation","Zip"],
    encoding="latin-1"
)

# Үнэлгээ: UserID::MovieID::Rating::Timestamp
ratings = pd.read_csv(
    os.path.join(DATA_DIR, "ratings.dat"),
    sep="::", engine="python",
    names=["UserID","MovieID","Rating","Timestamp"],
    encoding="latin-1"
)

# Кино: MovieID::Title::Genres
movies = pd.read_csv(
    os.path.join(DATA_DIR, "movies.dat"),
    sep="::", engine="python",
    names=["MovieID","Title","Genres"],
    encoding="latin-1"
)

# ХООСОН УТГА УСТГАХ
for df in [users, ratings, movies]:
    df.dropna(inplace=True)

# ДАВХАРДАЛ УСТГАХ
users.drop_duplicates("UserID", inplace=True)
ratings.drop_duplicates(["UserID", "MovieID"], inplace=True)
movies.drop_duplicates("MovieID", inplace=True)

# ХҮЧИНТЭЙ УТГУУД
ratings = ratings[ratings["Rating"].between(1, 5)]
valid_ages = [1, 18, 25, 35, 45, 50, 56]
users = users[users["Age"].isin(valid_ages)]

print(f"\n📊 Хэрэглэгч: {len(users):,}  |  Үнэлгээ: {len(ratings):,}  |  Кино: {len(movies):,}")

# ─────────────────────────────────────────────────────────
# 3. FEATURE ENGINEERING — хэрэглэгч тус бүрийн профайл
# ─────────────────────────────────────────────────────────
# Хэрэглэгч бүрийн үнэлгээний дүн
user_stats = ratings.groupby("UserID").agg(
    AvgRating   = ("Rating", "mean"),
    NumRatings  = ("Rating", "count"),
    RatingStd   = ("Rating", "std"),
).reset_index()
user_stats["RatingStd"] = user_stats["RatingStd"].fillna(0)

# Хамгийн их үнэлгээ өгсөн жанрыг олох
ratings_movies = ratings.merge(movies[["MovieID","Genres"]], on="MovieID")
ratings_movies["PrimaryGenre"] = ratings_movies["Genres"].str.split("|").str[0]
top_genre = (ratings_movies.groupby(["UserID","PrimaryGenre"])
                           .size()
                           .reset_index(name="cnt")
                           .sort_values("cnt", ascending=False)
                           .groupby("UserID")
                           .first()
                           .reset_index()[["UserID","PrimaryGenre"]])

# Бүгдийг нэгтгэх
df = users[["UserID", "Age", "Occupation", "Zip"]].merge(user_stats, on="UserID").merge(top_genre, on="UserID")

# Жанрыг тоо болгох
le = LabelEncoder()
genre_dummies = pd.get_dummies(df["PrimaryGenre"], prefix="Genre")
df = pd.concat([df, genre_dummies], axis=1)

print(f"✓  Feature engineering дуусав. Нийт хэрэглэгч: {len(df):,}")
print(df[["Age","AvgRating","NumRatings","RatingStd"]].describe().round(2))

# ─────────────────────────────────────────────────────────
# 4. SCALING + ELBOW + SILHOUETTE
# ─────────────────────────────────────────────────────────
features = ["Age","AvgRating","NumRatings","RatingStd"]
scaler   = StandardScaler()
X        = scaler.fit_transform(df[features])

inertias, silhouettes = [], []
K_range = range(2, 9)
print("\nElbow + Silhouette тооцоолж байна...")
for k in K_range:
    km   = KMeans(n_clusters=k, random_state=42, n_init=10)
    labs = km.fit_predict(X)
    inertias.append(km.inertia_)
    silhouettes.append(silhouette_score(X, labs, sample_size=3000, random_state=42))
    print(f"  K={k}  inertia={km.inertia_:,.0f}  silhouette={silhouettes[-1]:.3f}")

fig, axes = plt.subplots(1, 2, figsize=(14, 4))
fig.suptitle("Оновчтой K тодорхойлох — Бодит MovieLens 1M өгөгдөл дээр", fontsize=13, fontweight="bold")

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

# WatchCount дундаж-аар эрэмбэлж нэрлэх
order = df.groupby("Cluster")["NumRatings"].mean().sort_values(ascending=False).index.tolist()
remap = {old: new for new, old in enumerate(order)}
df["Cluster"] = df["Cluster"].map(remap)

CLUSTER_LABELS = ["Идэвхтэй залуу үзэгч", "Нарийн шүүмжлэгч",
                  "Дунд зэргийн үзэгч", "Хааяа нэг үздэг үзэгч"]

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


inverse_remap = {v:k for k,v in remap.items()}
ordered_centers = km_final.cluster_centers_[
    [inverse_remap[i] for i in range(K)]
]
centers_pca = pca.transform(ordered_centers)
ax.scatter(centers_pca[:,0], centers_pca[:,1],
           s=250, marker="*", color="white", edgecolors="black", linewidth=0.8,
           zorder=5, label="Кластерийн төв")

var = pca.explained_variance_ratio_
ax.set_xlabel(f"PCA 1  ({var[0]*100:.1f}%)", fontsize=11)
ax.set_ylabel(f"PCA 2  ({var[1]*100:.1f}%)", fontsize=11)
ax.set_title(f"K-Means кластер — PCA 2D проекц\nMovieLens 1M бодит өгөгдөл ({len(df):,} хэрэглэгч)", fontsize=13, fontweight="bold")
ax.legend(framealpha=0.2, fontsize=10)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(out("02_pca_scatter.png"), dpi=150, bbox_inches="tight")
plt.show()

# ─────────────────────────────────────────────────────────
# 7. RADAR CHART
# ─────────────────────────────────────────────────────────
radar_features = ["Age","AvgRating","NumRatings","RatingStd"]
radar_labels   = ["Нас","Дундаж үнэлгээ","Үнэлгээний тоо","Тогтворгүй байдал"]
summary = df.groupby("Cluster")[radar_features].mean()
norm = (summary - summary.min()) / (
    summary.max() - summary.min() + 1e-9
)

angles  = np.linspace(0, 2*np.pi, len(radar_features), endpoint=False).tolist()
angles += angles[:1]

fig, axes = plt.subplots(2, 2, figsize=(12, 10), subplot_kw=dict(polar=True))
fig.suptitle("Кластер бүрийн профайл — бодит MovieLens өгөгдөл", fontsize=14, fontweight="bold", y=1.01)

for i, ax in enumerate(axes.flat):
    vals = norm.loc[i].tolist() + norm.loc[i].tolist()[:1]
    ax.plot(angles, vals, color=PALETTE[i], linewidth=2.5)
    ax.fill(angles, vals, color=PALETTE[i], alpha=0.25)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(radar_labels, fontsize=9)
    ax.set_yticklabels([])
    ax.set_title(CLUSTER_LABELS[i], color=PALETTE[i], fontsize=12, fontweight="bold", pad=15)
    ax.grid(color="#2a2a45")
    raw = summary.loc[i]
    ax.annotate(
        f"Нас: {raw['Age']:.0f}  |  Үнэлгээ: {raw['AvgRating']:.2f}\nТоо: {raw['NumRatings']:.0f}  |  Тогтворгүй: {raw['RatingStd']:.2f}",
        xy=(0.5,-0.22), xycoords="axes fraction", ha="center", fontsize=9, color="#9090b0"
    )

plt.tight_layout()
plt.savefig(out("03_radar_profiles.png"), dpi=150, bbox_inches="tight")
plt.show()

# ─────────────────────────────────────────────────────────
# 8. ЖАНРЫН STACKED BAR
# ─────────────────────────────────────────────────────────
genre_cluster = (
    df.groupby(["Cluster","PrimaryGenre"])
      .size().unstack(fill_value=0)
      .div(df.groupby("Cluster").size(), axis=0)
)
top_genres_list = genre_cluster.sum().sort_values(ascending=False).head(8).index.tolist()
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
        if v > 0.06:
            ax.text(j, b+v/2, genre[:5], ha="center", va="center", fontsize=8, color="white", fontweight="bold")
    bottom += vals

ax.set_xticks(range(K))
ax.set_xticklabels([f"Бүлэг {i}\n{CLUSTER_LABELS[i]}" for i in range(K)], fontsize=10)
ax.set_ylabel("Жанрын эзлэх хувь")
ax.set_title("Кластер бүрийн дуртай жанрын хуваарилалт — бодит өгөгдөл", fontsize=13, fontweight="bold")
ax.legend(loc="upper right", bbox_to_anchor=(1.18,1), fontsize=9, framealpha=0.15)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x,_: f"{x:.0%}"))
ax.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig(out("04_genre_distribution.png"), dpi=150, bbox_inches="tight")
plt.show()

# ─────────────────────────────────────────────────────────
# 9. ДҮГНЭЛТ
# ─────────────────────────────────────────────────────────
print("\n" + "═"*58)
print("  КЛАСТЕРИЙН ДҮГНЭЛТ")
print("═"*58)
for c in range(K):
    sub = df[df["Cluster"]==c]
    top_g = sub["PrimaryGenre"].value_counts().head(3).index.tolist()
    print(f"\n🎬  Бүлэг {c} — {CLUSTER_LABELS[c]}  (n={len(sub):,})")
    print(f"   Дундаж нас       : {sub['Age'].mean():.1f}")
    print(f"   Үнэлгээний тоо   : {sub['NumRatings'].mean():.0f}")
    print(f"   Дундаж үнэлгээ   : {sub['AvgRating'].mean():.2f} / 5")
    print(f"   Үнэлгээний хэлбэлзэл: {sub['RatingStd'].mean():.2f}")
    print(f"   Дуртай жанрууд   : {', '.join(top_g)}")

print(f"\n✅  Бүх зурагнууд '{OUTPUT_DIR}' хавтаст хадгалагдлаа.")