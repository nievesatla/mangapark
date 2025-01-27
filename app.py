from flask import Flask, request, render_template
import requests
from bs4 import BeautifulSoup
import img2pdf

app = Flask(__name__)

@app.route('/')
def index():
  return render_template('index.html')

@app.route('/download-manga', methods=['POST'])
def download_manga():
  mangapark_url = request.form['mangapark-url']
  height = request.form['height']
  chapters = request.form['chapters']
  
  # Use Python libraries like requests and BeautifulSoup to scrape the mangapark website and extract the URLs of the individual chapters
  soup = BeautifulSoup(requests.get(mangapark_url).content, 'html.parser')
  chapter_urls = []
  for chapter in soup.find_all('a', {'class': 'chapters'}):
    chapter_urls.append(chapter['href'])
  
  # Download each chapter's images using the requests library and convert them into a PDF file using the img2pdf library
  with open('manga.pdf', 'wb') as f:
    for url in chapter_urls:
      image = requests.get(url, stream=True).content
      pdf = img2pdf.convert(image)
      f.write(pdf)
  
  return render_template('download-manga.html', mangapark_url=mangapark_url, height=height, chapters=chapters)

if __name__ == '__main__':
  app.run()