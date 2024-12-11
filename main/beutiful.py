from bs4 import BeautifulSoup
import requests
import pandas as pd
import os
import urllib.parse
import datetime
import time
from dotenv import load_dotenv

load_dotenv('../.env')

username = os.getenv('OXILAB_USERNAME')
password = os.getenv('OXILAB_PASSWORD')


def get_user_input():
    """
    Get job search parameters from user
    """
    # Get job title
    while True:
        job_title = input("Enter job title (e.g., web developer, data scientist): ").strip()
        if job_title:
            break
        print("Job title cannot be empty. Please try again.")
    
    # Get location (with default to Ahmedabad)
    location = input("Enter location (press Enter for default Ahmedabad, Gujarat): ").strip()
    
    # If location is empty, use default
    if not location:
        location = "Ahmedabad, Gujarat"
    
    # Get max rows to retrieve
    while True:
        try:
            max_rows = int(input("Enter maximum number of job listings to retrieve (1-100): "))
            if 1 <= max_rows <= 100:
                break
            print("Please enter a number between 1 and 100.")
        except ValueError:
            print("Invalid input. Please enter a number.")
    
    return job_title, location, max_rows

def construct_indeed_url(job_title, location, start=0):
    """
    Construct Indeed search URL with pagination
    """
    # URL encode job title and location
    encoded_job_title = urllib.parse.quote(job_title)
    encoded_location = urllib.parse.quote(location)
    
    # Construct URL with start parameter for pagination
    url = f"https://in.indeed.com/jobs?q={encoded_job_title}&l={encoded_location}"
    if start > 0:
        url += f"&start={start}"
    
    return url

def proxy_request(url):
    """
    Make request to Oxylabs API
    """
    try:
        payload = {"source": "universal", "url": url}
        
        response = requests.request(
            "POST",
            "https://realtime.oxylabs.io/v1/queries",
            auth=  (username, password),
            json=payload,
        )
        
        html_response = response.json()["results"][0]["content"]
        return BeautifulSoup(html_response, "html.parser")
    except requests.exceptions.RequestException as e:
        print("Error:", e)
        return None

def parse_job_listings(soup):
    """
    Parse job listings from soup object
    Returns job data and a boolean indicating if more pages exist
    """
    # Find all job card containers
    job_cards = soup.find_all('div', class_='job_seen_beacon')
    
    job_data = []
    
    for card in job_cards:
        # Extract job title
        job_title = card.find('h2', class_='jobTitle').get_text(strip=True) if card.find('h2', class_='jobTitle') else 'N/A'
        
        # Extract company name
        company_name_elem = card.find('span', {'data-testid': 'company-name'})
        company_name = company_name_elem.get_text(strip=True) if company_name_elem else 'N/A'
        
        # Extract location
        location_elem = card.find('div', {'data-testid': 'text-location'})
        location = location_elem.get_text(strip=True) if location_elem else 'N/A'
        
        # Extract full job description
        description_div = card.find('div', class_='heading6 tapItem-gutter css-ot0ljy eu4oa1w0')
        full_description = 'N/A'
        if description_div:
            description_list = description_div.find('ul')
            if description_list:
                # Extract text from list items
                description_points = [
                    li.get_text(strip=True) for li in description_list.find_all('li')
                ]
                
                # Join description points
                full_description = ' | '.join(description_points)
        
        job_info = {
            'Title': job_title,
            'Company': company_name,
            'Location': location,
            'Description': full_description
        }
        
        job_data.append(job_info)
    
    # Check if there are more pages
    next_page_link = soup.find('a', {'data-testid': 'pagination-page-next'})
    has_more_pages = next_page_link is not None
    
    return job_data, has_more_pages

def main():
    
    job_title, location, max_rows = get_user_input()

    all_job_data = []
    current_page = 0
    retrieved_jobs = 0
    
    while retrieved_jobs < max_rows:
        # Construct URL for current page
        url = construct_indeed_url(job_title, location, start=current_page * 10)
        
        # Scrape the job listings
        soup = proxy_request(url)
        
        if not soup:
            print("Failed to retrieve job listings.")
            break
    
        job_data, has_more_pages = parse_job_listings(soup)
        
        # Add to total job data
        all_job_data.extend(job_data)
        retrieved_jobs += len(job_data)
        
        # Break if no more pages or reached max rows
        if not has_more_pages or retrieved_jobs >= max_rows:
            break
        
        # Move to next page
        current_page += 1
        
        # Add a small delay to avoid overwhelming the server
        time.sleep(1)
    
    # Trim to max_rows if necessary
    all_job_data = all_job_data[:max_rows]
    
    df_jobs = pd.DataFrame(all_job_data)
    
    current_directory = os.getcwd()

    # Get parent directory
    main_directory = os.path.dirname(current_directory)

    # Get scraped_csv Directory
    scraped_csv_directory = os.path.join(main_directory, 'scraped_csv')

    # Create filename with job title and timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"web_scraped_{job_title.replace(' ', '_')}_{timestamp}.csv"
    csv_file_path = os.path.join(scraped_csv_directory, csv_filename)
    
    # Save to CSV
    df_jobs.to_csv(csv_file_path, index=False)
    
    print(f"Job listings saved to {csv_file_path}")
    print(f"\nRetrieved {len(df_jobs)} job listings:")
    print(df_jobs)

if __name__ == "__main__":
    main()