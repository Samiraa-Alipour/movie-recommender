import pandas as pd
import numpy as np
from scipy.sparse.linalg import svds
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict

class MovieRecommender:
    def __init__(self, ratings_file='ml-1m/ratings.dat', movies_file='ml-1m/movies.dat'):
        # Load data
        self.ratings_df = pd.read_csv(ratings_file,
                                    sep='::',
                                    engine='python',
                                    names=['UserID', 'MovieID', 'Rating', 'Timestamp'])

        self.movies_df = pd.read_csv(movies_file,
                                   sep='::',
                                   engine='python',
                                   names=['MovieID', 'Title', 'Genres'],
                                   encoding='latin-1')

        # Create user-item matrix
        self.user_item_matrix = self.ratings_df.pivot(
            index='UserID',
            columns='MovieID',
            values='Rating'
        ).fillna(0)

        # Train all models
        self.train_all_models()

    def train_all_models(self):
        self.train_user_user()
        self.train_item_item()
        self.train_svd()

    def train_user_user(self):
        # Compute user similarity matrix
        self.user_similarity = cosine_similarity(self.user_item_matrix)

    def train_item_item(self):
        # Compute item similarity matrix
        self.item_similarity = cosine_similarity(self.user_item_matrix.T)

    def train_svd(self, k=50):
        # Perform SVD
        U, sigma, Vt = svds(self.user_item_matrix.values, k=k)
        sigma = np.diag(sigma)
        self.svd_preds = np.dot(np.dot(U, sigma), Vt)

    def user_user_recommendations(self, user_id, n=10):
        if user_id not in self.user_item_matrix.index:
            return []

        user_idx = self.user_item_matrix.index.get_loc(user_id)
        user_similarities = self.user_similarity[user_idx]

        # Get weighted average of ratings
        weighted_avg = np.dot(user_similarities, self.user_item_matrix.values)
        weighted_avg = weighted_avg / (np.sum(np.abs(user_similarities)) + 1e-8)

        # Get movies user hasn't rated
        user_ratings = self.user_item_matrix.loc[user_id]
        unrated_movies = user_ratings[user_ratings == 0].index

        # Get top N recommendations
        recommendations = pd.Series(weighted_avg, index=self.user_item_matrix.columns)
        recommendations = recommendations[unrated_movies].sort_values(ascending=False)[:n]

        return recommendations.index.tolist()

    def item_item_recommendations(self, user_id, n=10):
        if user_id not in self.user_item_matrix.index:
            return []

        user_ratings = self.user_item_matrix.loc[user_id]
        weighted_sum = np.zeros(len(self.item_similarity))

        for item_id, rating in enumerate(user_ratings):
            if rating > 0:
                weighted_sum += rating * self.item_similarity[item_id]

        # Normalize
        weighted_sum = weighted_sum / (np.sum(np.abs(self.item_similarity), axis=1) + 1e-8)

        # Get unrated movies
        unrated_movies = user_ratings[user_ratings == 0].index

        # Get top N recommendations
        recommendations = pd.Series(weighted_sum, index=self.user_item_matrix.columns)
        recommendations = recommendations[unrated_movies].sort_values(ascending=False)[:n]

        return recommendations.index.tolist()

    def svd_recommendations(self, user_id, n=10):
        if user_id not in self.user_item_matrix.index:
            return []

        user_idx = self.user_item_matrix.index.get_loc(user_id)
        user_ratings = self.user_item_matrix.loc[user_id]

        # Get predictions for user
        user_preds = self.svd_preds[user_idx]

        # Get unrated movies
        unrated_movies = user_ratings[user_ratings == 0].index

        # Get top N recommendations
        recommendations = pd.Series(user_preds, index=self.user_item_matrix.columns)
        recommendations = recommendations[unrated_movies].sort_values(ascending=False)[:n]

        return recommendations.index.tolist()

    def ensemble_recommendations(self, user_id, n=10):
        # Get recommendations from all models
        uu_recs = self.user_user_recommendations(user_id, n=n)
        ii_recs = self.item_item_recommendations(user_id, n=n)
        svd_recs = self.svd_recommendations(user_id, n=n)

        # Combine recommendations using rank fusion
        movie_scores = defaultdict(float)

        for rank, movie_id in enumerate(uu_recs):
            movie_scores[movie_id] += 1.0 / (rank + 1)

        for rank, movie_id in enumerate(ii_recs):
            movie_scores[movie_id] += 1.0 / (rank + 1)

        for rank, movie_id in enumerate(svd_recs):
            movie_scores[movie_id] += 1.0 / (rank + 1)

        # Sort by score and return top N
        sorted_movies = sorted(movie_scores.items(), key=lambda x: x[1], reverse=True)
        return [movie_id for movie_id, _ in sorted_movies[:n]]

    def get_user_recommendations(self, user_id, n=10):
        # Fetch top 10 movies for this user using ensemble recommendations
        recommendations = self.ensemble_recommendations(user_id, n)
        return recommendations[:10]

    def get_movie_details(self, movie_ids):
        # Get movie details for the recommended movies
        return self.movies_df[self.movies_df['MovieID'].isin(movie_ids)].to_dict('records')