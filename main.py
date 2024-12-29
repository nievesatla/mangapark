"""
Mangapark-DL: Downloads manga and converts to PDF for the site www.mangapark.com

Example:
    Download chapter 20 for the manga Ajin Miura Tsuina
        $ python3 main.py -m http://mangapark.me/manga/ajin-miura-tsuina/ -chapter 20
"""
import re
import os
import sys
import argparse
import urllib.request
import img2pdf
from bs4 import BeautifulSoup
from PIL import Image
# from resizeimage import resizeimage
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import os
import time
import zipfile

# Ensure raw_images and final_output directories exist

def parse_url_to_manga_info(url):
    """
    Extracts the title of a manga from an URL.
    :param url: a string that denotes the URL
    :return: the title of a manga
    """

    url = re.sub('http://', '', url)
    url = re.sub('mangapark.me/manga/', '', url)
    title = url.split("/")[0]
    return title

def download_image_with_headers(img_url, dir_filename, os_dir):
    # Ensure the 'downloads' folder exists
    os.makedirs("downloads", exist_ok=True)

    # Extract the filename from the image URL if not provided
    filename = os.path.basename(dir_filename)  # Use the provided 'dir_filename' for filename

    # Join the 'downloads' folder with the image filename
    dir_filename = os.path.join(os_dir, filename)

    # Set a User-Agent to mimic a real browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
    }

    req = urllib.request.Request(img_url, headers=headers)

    # Download the image with the custom headers
    with urllib.request.urlopen(req) as response, open(dir_filename, 'wb') as out_file:
        out_file.write(response.read())

def parse_url_to_chapter_info(url):
    """
    Extract manga info from the URL, namely: (title, version, chapter, url)
    :param url: a string that denotes the URL
    :return: 4-tuple containing the manga's title, version, chapter and url
    """
    # Ensure there are no redundant slashes in the URL.
    url = url.strip()  # Remove leading/trailing whitespaces
    parsed_url = urlparse(url)
    
    # Fix if the URL contains an incorrect number of slashes or is relative
    if parsed_url.scheme == '' or parsed_url.netloc == '':
        url = 'https://mangapark.me/' + url.lstrip('/')  # Prepend the base URL

    # Clean up the URL by removing parts we don't need
    url = re.sub(r"^https?://", '', url)  # Remove http:// or https://
    url = re.sub(r"mangapark.me", '', url)  # Remove the domain part
    url = re.sub(r"/manga/", '', url)  # Remove the "/manga/" path part

    # Ensure the URL structure is correct
    url_parts = url.split("/")
    if len(url_parts) == 3:
        title, version, chapter = url_parts
    elif len(url_parts) == 4:
        title, _, version, chapter = url_parts
    else:
        print("The URL in question was: ", url)
        raise ValueError("Couldn't parse URL")

    return title, version, chapter, url


def ensure_directory_exist(directory):
    """
    Creates a directory, if it doesn't exist yet.
    :param directory: directory file path
    :return: None
    """
    if not os.path.exists(directory):
        os.makedirs(directory)


def download_image(path):
    """
    Reads an image from the specified source.
    :param path: file path of the image
    :return: raw image data in byte[]
    """

    if path == '-':
        raw_data = sys.stdin.buffer.read()
    else:
        try:
            with open(path, "rb") as im:
                raw_data = im.read()
        except IsADirectoryError:
            raise argparse.ArgumentTypeError(
                "\"%s\" is a directory" % path)
        except PermissionError:
            raise argparse.ArgumentTypeError(
                "\"%s\" permission denied" % path)
        except FileNotFoundError:
            raise argparse.ArgumentTypeError(
                "\"%s\" does not exist" % path)

    if len(raw_data) == 0:
        raise argparse.ArgumentTypeError("\"%s\" is empty" % path)

    return raw_data


def convert_to_pdf(os_dir, chapter, file_names):
    """
    Converts a collection of images to PDF format
    :param os_dir: Directory to save PDF in.
    :param chapter: Title of the PDF.
    :param file_names: Images to construct the PDF from.
    :return:
    """

    print("Converting chapter %s to pdf..." % chapter)

    image_paths = [os.path.join(os_dir, os.path.basename(path)) for path in file_names]

    # Debugging: Print the paths to verify correctness
    # print("Image paths for PDF conversion:", image_paths)
    
    # Ensure the 'downloads' folder exists
    os.makedirs("downloads", exist_ok=True)
    os.makedirs("finals", exist_ok=True)

    # Convert images to PDF using img2pdf
    pdf_bytes = img2pdf.convert(image_paths)
    output_pdf = os.path.join("finals", f"chapter_{chapter}.pdf")
    
    # Save the PDF file directly in the 'downloads' folder
    with open(output_pdf, "wb") as f:
        f.write(pdf_bytes)

    print(f"PDF saved as {output_pdf}")

def zip_final_pdfs(output_zip_path="finals/final_pdfs.zip"):
    pdf_folder = "finals"  # Your `finals` folder path
    with zipfile.ZipFile(output_zip_path, 'w') as zipf:
        for root, _, files in os.walk(pdf_folder):
            for file in files:
                if file.endswith(".pdf"):
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, pdf_folder)  # Preserve folder structure in the ZIP
                    zipf.write(file_path, arcname)
    print(f"PDFs zipped into {output_zip_path}")

def download_chapter(url, height):
    """
    Downloads the chapter specified by the url into your file directory
    :param url: string denoting the url
    :param height: int denoting the height of the image you want to download in
    :return: None.
    """
    if not url.startswith("http"):
        url = "https://mangapark.me" + url

    title, _, chapter, os_dir = parse_url_to_chapter_info(url)
    os_dir = os.path.join("downloads", title, f"chapter_{chapter}")
    os.makedirs(os_dir, exist_ok=True)

    # Set up Selenium WebDriver
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Run Chrome in headless mode (no UI)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        driver.get(url)  # Open the manga page

        # Wait for the "Close" button to appear and click it
        try:
            # Adjust the selector to target the "Close" button in the ad
            close_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//span[text()="Close"]'))
            )
            close_button.click()  # Click the "Close" button
            time.sleep(1)  # Wait a bit after clicking (optional)
        except Exception as e:
            print("No pop-up detected or failed to close pop-up:", e)

        # Now parse the page after closing the ad
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Find images after closing the pop-up
        imgs_wrappers = soup.find_all("img", {"class": "w-full h-full"})

        file_names = []
        for i in imgs_wrappers:
            img_url = strip_parameters_from_url(i['src'])
            filename = img_url.split('/')[-1]
            print(f"Downloading {title} {chapter} {filename}...")
            dir_filename = os.path.join(os_dir, filename)

            # Use the custom download method with headers
            download_image_with_headers(img_url, filename, os_dir)
            
            # If a resize function is defined, apply it
            new_dir_filename = resize(dir_filename, height)
            file_names.append(new_dir_filename)

        convert_to_pdf(os_dir, chapter, file_names)


    finally:
        driver.quit()  # Close the Selenium WebDriver


def strip_parameters_from_url(url):
    """
    Parses the URL and strips away the parameters
    :param url: string URL with parameters
    :return: string URL without parameters
    """
    return re.sub(r'\?.*', '', url)


def resize(filename, height=None):
    """
    Resize the image to a certain proportion by height
    :param filename: string path of file to the image
    :param height: int
    :return: new filename of the image
    """
    if height is None:
        return filename
    print("Resizing %s to %spx height..." % (filename, height))
    with open(filename, 'r+b') as f:
        with Image.open(f) as image:
            cover = resizeimage.resize_height(image, height)
            new_filename = filename + '.res'
            cover.save(new_filename, image.format)
    return new_filename


def download_manga(url, chapter=None, min_max=None, height=None):
    """
    Downloads the chapters of a manga
    :param url: string url of the manga
    :param chapter: int chapter to download. if no chapter is specified, the min_max parameter is used.
    :param min_max: the inclusive range of chapters to download, e.g [1,10] -> chapters 1 to 10
    :param height: The height to witch resize all images (keeping the aspect ratio)
    :return: None
    """

    page = urllib.request.urlopen(url)
    soup = BeautifulSoup(page, "html.parser")

    # streams = soup.find_all("div", {"class": "stream"})
    # if not streams:
    #     raise ValueError("No streams found on the page. Check the URL or website structure.")

    # stream_lens = []
    # for stream in streams:
    #     chapters = stream.find_all("li")
    #     stream_lens += [len(chapters)]

    # max_stream_len = max(stream_lens)
    # max_idx = stream_lens.index(max_stream_len)
    # best_stream = streams[max_idx]

    # #judging by the above script, there used to be a div called stream that, in the chapter select screen, would select the optimal server.
    # #today, it's within the chapter page where a different server can be picked; over the past 8 years stream quality is on the up.

    # chapters = best_stream.find_all("li")

    chapter_divs = soup.find_all("div", {"class": "space-x-1"})
    chapters = []

    for div in chapter_divs:
        chapter_link = div.find("a", {"class": "link-hover"})
        if chapter_link and "href" in chapter_link.attrs:
            chapter_url = chapter_link["href"]
            chapter_text = chapter_link.text.strip()

            # Check if the text starts with "Ch." or "Chapter"
            if chapter_text.startswith("Ch.") or chapter_text.startswith("Chapter"):
                try:
                    # Extract chapter number correctly
                    if chapter_text.startswith("Ch."):
                        chapter_no = int(chapter_text[3:])  # Ch. for earlier chapters
                    elif chapter_text.startswith("Chapter"):
                        chapter_no = int(chapter_text[7:].split(":")[0])  # Chapter for newer chapters, before the colon
                    chapters.append((chapter_no, chapter_url))
                except ValueError:
                    print(f"Skipping invalid chapter number: {chapter_text}")
                    continue


    #below removed in this update. No longer needed wiht the latest implementation
    # for c in chapters[::-1]:
    #     chapter_url = c.em.find_all("a")[-1]['href']
    #     chapter_no = float(parse_url_to_chapter_info(chapter_url)[2][1:])

    #     if chapter and chapter_no == chapter:
    #         download_chapter(chapter_url, height)
    #         break
    #     elif min_max and min_max[0] <= chapter_no <= min_max[1]:
    #         download_chapter(chapter_url, height)
    # Process each chapter based on the specified criteria

    for chapter_no, chapter_url in sorted(chapters, reverse=True):  # Sort by chapter number (descending)
        print(f"Processing Chapter {chapter_no}: {chapter_url}")

        if not chapter_url.startswith("https"):
            chapter_url = "https://mangapark.me" + chapter_url  # Add base URL

        # Validate and clean up URL
        chapter_url = chapter_url.replace("///", "//")  # Fix triple slashes if they exist

        if chapter and chapter_no == chapter:
            download_chapter(chapter_url, height)
            break
        elif min_max and min_max[0] <= chapter_no <= min_max[1]:
            download_chapter(chapter_url, height)
    zip_final_pdfs()


def main():
    """
    Downloads manga specified in command line based on the following arguments:
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--manga-url', help="The url of the mangapark manga to download")
    parser.add_argument('-s', '--size', '--height', type=int,
                        help='Height to resize images to (it will keep the aspect ratio)')
    parser.add_argument('-c', '--chapter', help="The chapter number that you specifically want to download")
    parser.add_argument('-cs', '--chapters', nargs=2, help="An inclusive range of chapters you want to download")

    args = parser.parse_args()
    print(args)

    if args.manga_url is None:
        print("Please specify the URL of the manga on mangapark.me")
        return

    elif args.chapters is not None:
        assert isinstance(args.chapters, list)
        download_manga(args.manga_url, min_max=[float(x) for x in args.chapters], height=args.size)

    elif args.chapter is not None:
        download_manga(args.manga_url, chapter=int(args.chapter), height=args.size)


if __name__ == "__main__":
    main()
