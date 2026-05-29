import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA

# =========================================================
# 1. DATA GENERATION (Жоохон зүй тогтолтой өгөгдөл үүсгэе)
# =========================================================
np.random.seed(42) # Үр дүнг ижил байлгах үүднээс
genres = ["Action", "Comedy", "Drama", "Sci-Fi", "Romance", "Horror", "Documentary", "Thriller", "Animation", "Fantasy"]
countries = ["USA", "Korean", "India", "China", "Japan", "Mongolia", "France", "Germany", "Italy", "Spain"]

data = {
    "Age": np.random.randint(18, 60, 1000),
    "Gender": np.random.choice(["Male", "Female"], 1000),
    "WatchHours": np.random.randint(1, 40, 1000),
    "FavoriteGenre": np.random.choice(genres, 1000),
    "Country": np.random.choice(countries, 1000),
    "Rating": np.round(np.random.uniform(1, 5, 1000), 1)
}

df = pd.DataFrame(data)

# =========================================================
# [ӨӨРЧЛӨЛТ] 4. FEATURE SEALING (Зөвхөн тоон багануудыг сонгох)
# =========================================================
# Жанр, улсыг оролцуулахгүй, зөвхөн үзэгчийн зан төлөвийн тоон үзүүлэлтийг авна
features_for_clustering = ["Age", "WatchHours", "Rating"]

scaler = StandardScaler()
scaled_data = scaler.fit_transform(df[features_for_clustering])

print("\nDATA SCALED SUCCESSFULLY FOR NUMERIC FEATURES!")

# =========================================================
# 5. ELBOW METHOD
# =========================================================
inertia = []
for k in range(1, 11):
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    kmeans.fit(scaled_data)
    inertia.append(kmeans.inertia_)

plt.figure(figsize=(8, 4))
plt.plot(range(1, 11), inertia, marker='o', color='purple')
plt.xlabel("Number of Clusters (K)")
plt.ylabel("Inertia")
plt.title("Elbow Method (Numeric Features)")
plt.show()

# =========================================================
# 6. TRAIN K-MEANS (Elbow-оос хараад K=4 эсвэл 3-ыг сонговол тохиромжтой)
# =========================================================
optimal_k = 4  # Тоон үзүүлэлтээр хийхэд 4 ихэвчлэн тохирдог
kmeans = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
clusters = kmeans.fit_predict(scaled_data)

df["Cluster"] = clusters

# =========================================================
# 7. VISUALIZATION (Watch Hours vs Age)
# =========================================================
plt.figure(figsize=(8, 5))
scatter = plt.scatter(df["Age"], df["WatchHours"], c=df["Cluster"], cmap='viridis', alpha=0.6)
plt.xlabel("Age")
plt.ylabel("Watch Hours")
plt.title("Нас болон Үзсэн цагийн хамаарал")
plt.colorbar(scatter)
plt.show()


# Графикийн хэмжээг тохируулах
plt.figure(figsize=(14, 7))

# Баганан график зурах
sns.barplot(
    data=df, 
    x="FavoriteGenre", 
    y="WatchHours", 
    hue="Cluster", 
    palette="viridis"
)

plt.xlabel("Дуртай жанр (Favorite Genre)", fontsize=12)
plt.ylabel("Дундаж үзсэн цаг (Average Watch Hours)", fontsize=12)
plt.title("Жанр болон Үзсэн цагийн хамаарал (Кластераар)", fontsize=14)
plt.xticks(rotation=45) # Жанрын нэрнүүдийг 45 градус налуулах
plt.grid(axis='y', linestyle='--', alpha=0.7)

plt.tight_layout()
plt.show()



plt.figure(figsize=(14, 7))

# Хайрцган график зурах
sns.boxplot(
    data=df, 
    x="FavoriteGenre", 
    y="WatchHours", 
    hue="Cluster", 
    palette="Set2"
)

plt.xlabel("Дуртай жанр (Favorite Genre)", fontsize=12)
plt.ylabel("Үзсэн цагийн тархалт (Watch Hours Distribution)", fontsize=12)
plt.title("Жанр болон Үзсэн цагийн тархалт (Кластераар)", fontsize=14)
plt.xticks(rotation=45)
plt.grid(axis='y', linestyle='--', alpha=0.5)

plt.tight_layout()
plt.show()

# =========================================================
# 9. CLUSTER ANALYSIS
# =========================================================
print("\nCLUSTER SUMMARY (MEAN VALUES):\n")
cluster_summary = df.groupby("Cluster")[features_for_clustering].mean()
print(cluster_summary)

# Клустер бүрт ямар жанр, улс давамгайлж байгааг харах
print("\nMOST COMMON GENRES IN EACH CLUSTER:\n")
for cluster in sorted(df["Cluster"].unique()):
    print(f"Cluster {cluster} Favorite Genre:")
    print(df[df["Cluster"] == cluster]["FavoriteGenre"].value_counts().head(2))
    print("-" * 30)