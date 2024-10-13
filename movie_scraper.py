import pandas as pd
import requests
from bs4 import BeautifulSoup
import os
import time
import json

class MovieImageScraper:
    def __init__(self):
        self.base_url = "https://www.themoviedb.org/search"
        # Remove this line as we don't need to prepend the image URL
        # self.image_base_url = "https://image.tmdb.org/t/p/w500"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
    def get_movie_image(self, movie_title, year=None):
        try:
            search_query = f"{movie_title}"
            if year:
                search_query += f" {year}"
            
            params = {"query": search_query}
            response = requests.get(self.base_url, params=params, headers=self.headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find the first movie poster
            poster = soup.find('img', class_='poster')
            if poster and 'src' in poster.attrs:
                # Return the URL directly without prepending
                return poster['src']
        except Exception as e:
            print(f"Error fetching image for {movie_title}: {e}")
        return None

def main():
    # Create directories if they don't exist
    os.makedirs('static/movie_posters', exist_ok=True)
    os.makedirs('static/user_avatars', exist_ok=True)
    
    # Load MovieLens dataset
    movies_df = pd.read_csv('ml-1m/movies.dat', 
                           sep='::', 
                           engine='python',
                           names=['MovieID', 'Title', 'Genres'],
                           encoding='latin-1')
    
    # Extract year from title and clean title
    movies_df['Year'] = movies_df['Title'].str.extract(r'\((\d{4})\)')
    movies_df['Clean_Title'] = movies_df['Title'].str.replace(r'\s*\(\d{4}\)', '')
    
    # Initialize scraper
    scraper = MovieImageScraper()
    
    # Dictionary to store movie information
    movie_info = {}
    
    # Scrape movie posters
    for idx, row in movies_df.iterrows():
        movie_id = row['MovieID']
        title = row['Clean_Title']
        year = row['Year']
        
        image_url = scraper.get_movie_image(title, year)
        if image_url:
            # Save image URL
            movie_info[movie_id] = {
                'title': title,
                'year': year,
                'image_url': image_url,
                'genres': row['Genres']
            }
        
        # Sleep to avoid overwhelming the server
        time.sleep(1)
        
        if idx % 10 == 0:
            print(f"Processed {idx} movies...")
    
    # Generate random user avatars using DiceBear API
    users_df = pd.read_csv('ml-1m/users.dat', 
                          sep='::', 
                          engine='python',
                          names=['UserID', 'Gender', 'Age', 'Occupation', 'Zip-code'])
    
    user_info = {}
    faker = Faker()
    
    for _, row in users_df.iterrows():
        user_id = row['UserID']
        # Generate a random avatar URL using DiceBear
        avatar_style = ['avataaars', 'bottts', 'identicon'][user_id % 3]
        avatar_url = f"https://api.dicebear.com/6.x/{avatar_style}/svg?seed={user_id}"
        
        user_info[user_id] = {
            'avatar_url': avatar_url,
            'fake_name': faker.name()
        }
    
    # Save information to JSON files
    with open('static/movie_info.json', 'w') as f:
        json.dump(movie_info, f)
    
    with open('static/user_info.json', 'w') as f:
        json.dump(user_info, f)

if __name__ == "__main__":
    main()