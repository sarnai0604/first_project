import os
import warnings
os.environ["OMP_NUM_THREADS"] = "4"
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.colors import LinearSegmentedColormap
import seaborn as sns

from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score

# Файл хадгалах хавтас — скриптийн байгаа директорт хадгална
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
def out(name):
    return os.path.join(OUTPUT_DIR, name)

# ─────────────────────────────────────────────────────────
# 0. STYLE SETUP
# ─────────────────────────────────────────────────────────
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

PALETTE = ["#7b5cfa", "#fa5c7b", "#5cfabd", "#fac85c", "#5cb8fa", "#fa935c"]
CLUSTER_LABELS = ["Бинж-вотч хийгч", "Насанд хүрсэн эрэгтэй", "Залуу эмэгтэй", "Чанарт кинонд дурлагч"]

# ─────────────────────────────────────────────────────────
# 1. БОДИТ ЗҮЙ ТОГТОЛТОЙ ӨГӨГДӨЛ ҮҮСГЭХ
#    4 тодорхой хэрэглэгчийн дүр тус бүрд 250 хүн
# ─────────────────────────────────────────────────────────
np.random.seed(42)
genres = ["Action", "Comedy", "Drama", "Sci-Fi", "Romance",
          "Horror", "Documentary", "Thriller", "Animation", "Fantasy"]

def make_group(n, age_mu, age_sd, hours_mu, hours_sd, rating_mu,
               genre_weights, gender_bias):
    ages        = np.clip(np.random.normal(age_mu,   age_sd,   n), 18, 65).astype(int)
    hours       = np.clip(np.random.normal(hours_mu, hours_sd, n),  1, 60).astype(int)
    ratings     = np.clip(np.random.normal(rating_mu, 0.6,     n),  1,  5)
    fav_genres  = np.random.choice(genres, n, p=genre_weights)
    genders     = np.random.choice(["Male", "Female"], n,
                                   p=[gender_bias, 1 - gender_bias])
    return ages, hours, ratings, fav_genres, genders

# Бүлэг 0 — Бинж-вотч хийгч (залуу, маш их үздэг, экшн/sci-fi)
g0 = make_group(250, 24, 4, 35, 6, 3.5,
    [.22,.08,.05,.20,.05,.08,.02,.12,.10,.08], 0.55)

# Бүлэг 1 — Насанд хүрсэн эрэгтэй (дундаж нас, баримтат/триллер)
g1 = make_group(250, 42, 7, 12, 4, 4.1,
    [.10,.08,.15,.08,.04,.06,.20,.18,.04,.07], 0.70)

# Бүлэг 2 — Залуу эмэгтэй (романс/комеди, дундаж цаг)
g2 = make_group(250, 27, 5, 20, 5, 3.8,
    [.05,.18,.12,.04,.25,.06,.03,.06,.12,.09], 0.20)

# Бүлэг 3 — Чанарт кинонд дурлагч (өндөр нас, өндөр үнэлгээ, дитектив/драма)
g3 = make_group(250, 50, 6, 8, 3, 4.7,
    [.04,.06,.28,.04,.08,.03,.10,.20,.02,.15], 0.50)

all_ages   = np.concatenate([g0[0], g1[0], g2[0], g3[0]])
all_hours  = np.concatenate([g0[1], g1[1], g2[1], g3[1]])
all_rating = np.concatenate([g0[2], g1[2], g2[2], g3[2]])
all_genres = np.concatenate([g0[3], g1[3], g2[3], g3[3]])
all_gender = np.concatenate([g0[4], g1[4], g2[4], g3[4]])

df = pd.DataFrame({
    "Age": all_ages,
    "WatchHours": all_hours,
    "Rating": np.round(all_rating, 1),
    "FavoriteGenre": all_genres,
    "Gender": all_gender,
})
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

print(f"Өгөгдлийн хэмжээ: {df.shape}")
print(df.head())

# ─────────────────────────────────────────────────────────
# 2. FEATURE ENGINEERING
#    Жанрыг тоон болгож, 5 feature ашиглана
# ─────────────────────────────────────────────────────────
le = LabelEncoder()
df["GenreEncoded"] = le.fit_transform(df["FavoriteGenre"])
df["GenderEncoded"] = (df["Gender"] == "Male").astype(int)

features = ["Age", "WatchHours", "Rating", "GenreEncoded", "GenderEncoded"]
scaler   = StandardScaler()
X_scaled = scaler.fit_transform(df[features])

# ─────────────────────────────────────────────────────────
# 3. ELBOW + SILHOUETTE — хамтад нь харуулна
# ─────────────────────────────────────────────────────────
inertias, silhouettes = [], []
K_range = range(2, 10)
for k in K_range:
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labs = km.fit_predict(X_scaled)
    inertias.append(km.inertia_)
    silhouettes.append(silhouette_score(X_scaled, labs))

fig, axes = plt.subplots(1, 2, figsize=(14, 4))
fig.suptitle("Оновчтой K-г тодорхойлох", fontsize=14, fontweight="bold", y=1.02)

ax1 = axes[0]
ax1.plot(K_range, inertias, "o-", color=PALETTE[0], linewidth=2, markersize=7)
ax1.axvline(4, color=PALETTE[1], linestyle="--", alpha=0.7, label="K=4 сонголт")
ax1.set_xlabel("Кластерийн тоо (K)")
ax1.set_ylabel("Инерци (Inertia)")
ax1.set_title("Elbow Method")
ax1.legend()
ax1.grid(True)

ax2 = axes[1]
ax2.plot(K_range, silhouettes, "s-", color=PALETTE[2], linewidth=2, markersize=7)
ax2.axvline(4, color=PALETTE[1], linestyle="--", alpha=0.7, label="K=4 сонголт")
ax2.set_xlabel("Кластерийн тоо (K)")
ax2.set_ylabel("Silhouette Score")
ax2.set_title("Silhouette Score (өндөр = сайн)")
ax2.legend()
ax2.grid(True)

plt.tight_layout()
plt.savefig(out("01_elbow_silhouette.png"), dpi=150, bbox_inches="tight")
plt.show()
print("✓ 01_elbow_silhouette.png хадгалагдлаа")

# ─────────────────────────────────────────────────────────
# 4. K-MEANS СУРГАЛТ  (K=4)
# ─────────────────────────────────────────────────────────
optimal_k = 4
kmeans    = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
df["Cluster"] = kmeans.fit_predict(X_scaled)

sil = silhouette_score(X_scaled, df["Cluster"])
print(f"\nСонгосон K={optimal_k} — Silhouette Score: {sil:.3f}")

# Кластерийн дарааллыг WatchHours дундаж-аар эрэмбэлж нэрлэнэ
order = df.groupby("Cluster")["WatchHours"].mean().sort_values(ascending=False).index.tolist()
remap = {old: new for new, old in enumerate(order)}
df["Cluster"] = df["Cluster"].map(remap)
df["ClusterName"] = df["Cluster"].map({i: CLUSTER_LABELS[i] for i in range(4)})

# ─────────────────────────────────────────────────────────
# 5. PCA 2D SCATTER — кластерийг нүдээр харах
# ─────────────────────────────────────────────────────────
pca   = PCA(n_components=2, random_state=42)
X_pca = pca.fit_transform(X_scaled)
df["PCA1"] = X_pca[:, 0]
df["PCA2"] = X_pca[:, 1]

fig, ax = plt.subplots(figsize=(10, 7))
for c in range(optimal_k):
    mask = df["Cluster"] == c
    ax.scatter(df.loc[mask, "PCA1"], df.loc[mask, "PCA2"],
               color=PALETTE[c], alpha=0.55, s=35, label=CLUSTER_LABELS[c], zorder=2)

# Төвүүдийг PCA орон зайд проекцлох
centers_pca = pca.transform(kmeans.cluster_centers_[order])
ax.scatter(centers_pca[:, 0], centers_pca[:, 1],
           s=220, marker="*", color="white", edgecolors="black",
           linewidth=0.8, zorder=5, label="Кластерийн төв")

var = pca.explained_variance_ratio_
ax.set_xlabel(f"PCA 1  ({var[0]*100:.1f}% өөрчлөлтийг тайлбарлана)", fontsize=11)
ax.set_ylabel(f"PCA 2  ({var[1]*100:.1f}% өөрчлөлтийг тайлбарлана)", fontsize=11)
ax.set_title("K-Means кластер — PCA 2D проекц\n(хэмжилт бүрийн нийт тайлбарлах чадвар: "
             f"{sum(var)*100:.1f}%)", fontsize=13, fontweight="bold")
ax.legend(framealpha=0.2, fontsize=10)
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(out("02_pca_scatter.png"), dpi=150, bbox_inches="tight")
plt.show()
print("✓ 02_pca_scatter.png хадгалагдлаа")

# ─────────────────────────────────────────────────────────
# 6. RADAR CHART — кластер бүрийн профайл
# ─────────────────────────────────────────────────────────
radar_features = ["Age", "WatchHours", "Rating"]
summary = df.groupby("Cluster")[radar_features].mean()

# 0–1 нормчлол
norm = (summary - summary.min()) / (summary.max() - summary.min())

angles = np.linspace(0, 2 * np.pi, len(radar_features), endpoint=False).tolist()
angles += angles[:1]

fig, axes = plt.subplots(2, 2, figsize=(12, 10),
                         subplot_kw=dict(polar=True))
fig.suptitle("Кластер бүрийн профайл (Radar chart)", fontsize=14,
             fontweight="bold", y=1.01)

for idx, ax in enumerate(axes.flat):
    vals = norm.loc[idx].tolist() + norm.loc[idx].tolist()[:1]
    ax.plot(angles, vals, color=PALETTE[idx], linewidth=2.5)
    ax.fill(angles, vals, color=PALETTE[idx], alpha=0.25)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(["Нас", "Үзэх цаг", "Үнэлгээ"], fontsize=10)
    ax.set_yticklabels([])
    ax.set_title(CLUSTER_LABELS[idx], color=PALETTE[idx],
                 fontsize=12, fontweight="bold", pad=15)
    ax.grid(color="#2a2a45", linewidth=0.8)
    ax.spines["polar"].set_color("#2a2a45")
    raw = summary.loc[idx]
    ax.annotate(
        f"Нас: {raw['Age']:.0f}\nЦаг: {raw['WatchHours']:.0f}ц\nҮнэлгээ: {raw['Rating']:.2f}",
        xy=(0.5, -0.18), xycoords="axes fraction",
        ha="center", fontsize=9, color="#9090b0"
    )

plt.tight_layout()
plt.savefig(out("03_radar_profiles.png"), dpi=150, bbox_inches="tight")
plt.show()
print("✓ 03_radar_profiles.png хадгалагдлаа")

# ─────────────────────────────────────────────────────────
# 7. ЖАНРЫН ХУВААРИЛАЛТ — stacked bar (hue биш)
# ─────────────────────────────────────────────────────────
genre_cluster = (
    df.groupby(["Cluster", "FavoriteGenre"])
      .size()
      .unstack(fill_value=0)
      .div(df.groupby("Cluster").size(), axis=0)  # хувь болгоно
)

fig, ax = plt.subplots(figsize=(13, 6))
bottom = np.zeros(optimal_k)
genre_colors = plt.cm.tab10(np.linspace(0, 1, len(genres)))

for i, genre in enumerate(genres):
    vals = genre_cluster[genre].values
    bars = ax.bar(range(optimal_k), vals, bottom=bottom,
                  color=genre_colors[i], label=genre, width=0.55)
    # Том хэсгийн дотор нэр бичнэ
    for j, (v, b) in enumerate(zip(vals, bottom)):
        if v > 0.07:
            ax.text(j, b + v / 2, genre[:4], ha="center", va="center",
                    fontsize=8, color="white", fontweight="bold")
    bottom += vals

ax.set_xticks(range(optimal_k))
ax.set_xticklabels([f"Бүлэг {i}\n{CLUSTER_LABELS[i]}" for i in range(optimal_k)],
                   fontsize=10)
ax.set_ylabel("Жанрын эзлэх хувь")
ax.set_title("Кластер бүрийн дуртай жанрын хуваарилалт", fontsize=13, fontweight="bold")
ax.legend(loc="upper right", bbox_to_anchor=(1.18, 1), fontsize=9, framealpha=0.15)
ax.grid(axis="y", alpha=0.3)
ax.set_ylim(0, 1.05)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))

plt.tight_layout()
plt.savefig(out("04_genre_distribution.png"), dpi=150, bbox_inches="tight")
plt.show()
print("✓ 04_genre_distribution.png хадгалагдлаа")

# ─────────────────────────────────────────────────────────
# 8. CLUSTER SUMMARY ХЭВЛЭХ
# ─────────────────────────────────────────────────────────
print("\n" + "═"*55)
print("  КЛАСТЕРИЙН ДҮГНЭЛТ")
print("═"*55)
for c in range(optimal_k):
    sub = df[df["Cluster"] == c]
    top_genres = sub["FavoriteGenre"].value_counts().head(3)
    gender_ratio = sub["Gender"].value_counts(normalize=True)
    print(f"\n🎬  Бүлэг {c} — {CLUSTER_LABELS[c]}  (n={len(sub)})")
    print(f"   Дундаж нас    : {sub['Age'].mean():.1f}")
    print(f"   Үзэх цаг/7хон : {sub['WatchHours'].mean():.1f}")
    print(f"   Дундаж үнэлгээ: {sub['Rating'].mean():.2f}")
    print(f"   Эрэгтэй/Эмэгтэй: {gender_ratio.get('Male',0)*100:.0f}% / {gender_ratio.get('Female',0)*100:.0f}%")
    print(f"   Дуртай жанрууд: {', '.join(top_genres.index.tolist())}")

print(f"\n✅  Бүх дүрслэлүүд '{OUTPUT_DIR}' хавтасд хадгалагдлаа.")