from flask import Flask, render_template, request, jsonify
import json
from recommender import MovieRecommender
import os
import random
from collections import defaultdict
import requests
import re

app = Flask(__name__)

# Load movie and user information
with open('static/movie_info.json', 'r') as f:
    movie_info = json.load(f)

with open('static/user_info.json', 'r') as f:
    user_info = json.load(f)

# Initialize recommender
recommender = MovieRecommender()

# TMDB API setup
TMDB_API_KEY = '241350e227d6f49b985dba2d774a40d1'
TMDB_BASE_URL = 'https://api.themoviedb.org/3'

# def format_movie_title(title):
#     if title.lower().startswith('the '):
#         return title
#     else:
#         return re.sub(r'^(.*?), The$', r'The \1', title, flags=re.IGNORECASE)

# app.jinja_env.filters['format_movie_title'] = format_movie_title


def fetch_movie_details_from_tmdb(movie_title):
    """Fetch movie details from TMDB using the movie title."""
    search_url = f'{TMDB_BASE_URL}/search/movie?api_key={TMDB_API_KEY}&query={movie_title}'
    response = requests.get(search_url)
    
    if response.status_code == 200:
        data = response.json()
        if data['results']:
            movie_id = data['results'][0]['id']
            movie_details_url = f'{TMDB_BASE_URL}/movie/{movie_id}?api_key={TMDB_API_KEY}&append_to_response=credits'
            movie_response = requests.get(movie_details_url)
            if movie_response.status_code == 200:
                return movie_response.json()
    
    return None  # Return None if no movie is found or an error occurs

@app.route('/movie_api/<movie_title>', methods=['GET'])
def get_movie_details(movie_title):
    """Fetch movie details from the TMDB API by title and return as JSON."""
    movie_details = fetch_movie_details_from_tmdb(movie_title)
    
    if movie_details:
        # Extract relevant information
        movie_data = {
            'title': movie_details.get('title', 'N/A'),
            'year': movie_details.get('release_date', 'N/A').split('-')[0] if 'release_date' in movie_details else 'N/A',
            'genres': ', '.join([genre['name'] for genre in movie_details.get('genres', [])]) if movie_details.get('genres') else 'Unknown',
            'description': movie_details.get('overview', 'No description available for this movie.'),
            'duration': f"{movie_details.get('runtime', 'N/A')} min",
            'director': 'Unknown',
            'cast': []
        }
        
        # Get the director from credits
        if 'credits' in movie_details and movie_details['credits'].get('crew'):
            for crew_member in movie_details['credits']['crew']:
                if crew_member['job'] == 'Director':
                    movie_data['director'] = crew_member['name']
                    break
        
        # Get the top 3 cast members
        if 'credits' in movie_details and movie_details['credits'].get('cast'):
            top_cast = movie_details['credits']['cast'][:3]
            movie_data['cast'] = [actor['name'] for actor in top_cast]
        
        return jsonify(movie_data)
    
    # If no movie details were found, return a fallback
    return jsonify({
        'title': movie_title,
        'year': 'N/A',
        'genres': 'Unknown',
        'description': 'No description available for this movie.',
        'duration': 'Unknown',
        'director': 'Unknown',
        'cast': []
    })

# Function to get movie info
def get_movie_info(movie_id):
    """Safely get movie info with fallback for missing movies"""
    movie_id_str = str(movie_id)
    if movie_id_str in movie_info:
        return {
            **movie_info[movie_id_str],
            'movie_id': movie_id_str  # Add movie_id to the returned info
        }
    else:
        return {
            'movie_id': movie_id_str,
            'title': f'Movie {movie_id}',
            'year': 'N/A',
            'genres': 'Unknown',
            'image_url': 'https://via.placeholder.com/500x750?text=No+Poster',
            'description': 'No description available for this movie.',
            'rating': 'N/A',
            'director': 'Unknown',
            'cast': [],
            'duration': 'Unknown'
        }

def get_top_movies(n=5):
    """Get top N movies based on average rating with available details"""
    movie_ratings = defaultdict(list)
    for _, row in recommender.ratings_df.iterrows():
        movie_ratings[row['MovieID']].append(row['Rating'])
    
    # Calculate average ratings
    avg_ratings = {
        movie_id: sum(ratings)/len(ratings) 
        for movie_id, ratings in movie_ratings.items()
        if len(ratings) > 50  # Only consider movies with sufficient ratings
    }
    
    # Get top movies with available details
    top_movies = []
    for movie_id, avg_rating in sorted(avg_ratings.items(), key=lambda x: x[1], reverse=True):
        movie_info = get_movie_info(movie_id)
        if not movie_info['title'].startswith('Movie '):
            top_movies.append(movie_info)
            if len(top_movies) == n:
                break
    
    return top_movies

@app.route('/')
def index():
    # Get list of users and top movies for slider
    users = sorted(user_info.keys())
    top_movies = get_top_movies()
    return render_template('index.html', 
                         users=users, 
                         user_info=user_info, 
                         top_movies=top_movies)

@app.route('/featured')
def featured_movies():
    # Get top movies for the slider
    top_movies = get_top_movies(n=5)  # Adjust the number of movies as needed
    return render_template('featured.html', top_movies=top_movies)

@app.route('/user/<user_id>')
def user_recommendations(user_id):
    user_id = int(user_id)
    
    try:
        # Get recommendations from different models
        n_recommendations = 15  # Increased to support pagination
        
        user_user_recs = recommender.user_user_recommendations(user_id, n_recommendations)
        item_item_recs = recommender.item_item_recommendations(user_id, n_recommendations)
        # svd_recs = recommender.svd_recommendations(user_id, n_recommendations)
        ensemble_recs = recommender.ensemble_recommendations(user_id, n_recommendations)
        
        # Get movie information for recommendations
        # recommendations = {
        #     'User-Based': [get_movie_info(movie_id) for movie_id in user_user_recs],
        #     'Item-Based': [get_movie_info(movie_id) for movie_id in item_item_recs],
        #     'SVD': [get_movie_info(movie_id) for movie_id in svd_recs],
        #     'Ensemble': [get_movie_info(movie_id) for movie_id in ensemble_recs]
        # }
        # In the user_recommendations function, change the keys of the recommendations dictionary:
        recommendations = {
            'Movies You Might Like': [get_movie_info(movie_id) for movie_id in user_user_recs],
            'Similar to Your Favorites': [get_movie_info(movie_id) for movie_id in item_item_recs],
            'Top Picks for You': [get_movie_info(movie_id) for movie_id in ensemble_recs]
        }
        
        return render_template(
            'user.html',
            user_id=user_id,
            user_info=user_info[str(user_id)],
            recommendations=recommendations
        )
    except Exception as e:
        print(f"Error generating recommendations for user {user_id}: {str(e)}")
        return render_template(
            'error.html',
            error_message="Sorry, we couldn't generate recommendations for this user at the moment."
        )

@app.route('/movie/<movie_id>')
def movie_details(movie_id):
    """Endpoint to get detailed movie information"""
    movie = get_movie_info(movie_id)
    
    # Enhance movie details with additional information
    movie_ratings = recommender.ratings_df[
        recommender.ratings_df['MovieID'] == int(movie_id)
    ]['Rating']
    
    if len(movie_ratings) > 0:
        movie['average_rating'] = round(movie_ratings.mean(), 1)
        movie['num_ratings'] = len(movie_ratings)
    else:
        movie['average_rating'] = 'N/A'
        movie['num_ratings'] = 0
        
    return jsonify(movie)


if __name__ == '__main__':
    app.run(debug=True)
