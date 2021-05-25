"""
Noodle

Create clones of Moodle environments with all resources for archival purposes.
"""

import io
import os
import re
import shutil
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from urllib3.exceptions import InsecureRequestWarning

import parameters

if not os.path.exists('output'):
    os.makedirs('output')


class Auth():
    def login(self):
        self.s = requests.Session()

        payload = {
            "username": parameters.username,
            "password": parameters.password,
            "execution": parameters.execution,
            "_eventId": "submit"
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        # Suppress only the single warning from urllib3 needed.
        requests.packages.urllib3.disable_warnings(
            category=InsecureRequestWarning)

        r = self.s.post(url=parameters.url_auth, data=payload,
                        headers=headers, verify=False)


a = Auth()


def fetch_course(course_id, section=""):
    """
    Tests a provided course ID to ensure the user has access
    """

    url = parameters.url_moodle + "/course/view.php"
    params = {
        "id": course_id,
        "section": section
    }

    r = a.s.get(url, params=params)

    soup = BeautifulSoup(r.text, 'html.parser')
    page_title = soup.title.string

    if not page_title.startswith("Course"):
        save_soup(soup, os.path.join("output", "error.html"))
        raise Exception(
            "The course gave an error, the error page has been saved to error.html")

    else:
        return soup


def save_page(soup, subdir=""):
    """
    Parses and saves the course to its own subfolder.
    """
    page_title = soup.title.string.strip()

    if not subdir:
        course_title = re.search(r"Course: ([\w\W]+)", page_title)[1]
        course_path = os.path.join("output", course_title)
    else:
        course_title = re.search(r"Topic: ([\w\W]+)", page_title)[1]
        course_path = os.path.join("output", subdir, "resources", course_title)

    course_path = re.sub(r"[~#%&*{}:<>?|\"-]", "", course_path)
    course_path = re.sub(r" +", " ", course_path)

    course_title = re.sub(r"[~#%&*{}:<>?|\"-]", "", course_title)
    course_title = re.sub(r" +", " ", course_title)

    print(f"Found course: {course_title}")

    # Only overwrite if no subdir
    if os.path.exists(course_path):
        if not subdir:
            print("Course folder already found: recreating...")
            print("")
            shutil.rmtree(course_path)
        else:
            print(f"Subdir already exists: {course_path}")
            return course_title

    # Create the folder
    os.makedirs(os.path.join(course_path, "resources"))
    os.makedirs(os.path.join(course_path, "img"))
    os.makedirs(os.path.join(course_path, "css"))
    os.makedirs(os.path.join(course_path, "js"))

    # Save the raw course page for checking
    save_soup(soup, os.path.join(
        course_path, "resources", "index_raw.html"))

    # Select all links, and filter to only include links to a /resource/ suburl
    all_links = soup.find_all('a')
    resource_links = []

    print("Parsing links in file...")
    for link in tqdm(all_links):
        try:
            if re.search(r"/resource/|/page/|course[\w\W]+section=\d+", link.get('href')):
                resource_links.append(link)
        except TypeError:
            # The link has no destination, ignore it
            pass

    # Now do the same for inline images
    all_images = soup.find_all('img')
    resource_images = all_images

    print("")
    print(
        f"Found {len(resource_links)} resources and {len(resource_images)} images to fetch!")

    print("Downloading external links...")
    for resource in tqdm(resource_links):
        url = resource.get('href')

        # Check if a subpage instead of a normal file (only recurse once)
        is_section = re.search(r"course[\w\W]+section=\d+", url)

        if subdir or not is_section:
            file_id = re.search(r"id=(\d+)", url)[1]

            r = a.s.get(url)

            # Converts response headers mime type to an extension (may not work with everything)
            ext = r.headers['content-type'].split('/')[-1]
            ext = correct_extension_mimetype(ext)

            new_path = os.path.join("resources", f"{file_id}.{ext}")

            # Open the file to write as binary - replace 'wb' with 'w' for text files
            success = False
            while not success:
                try:
                    with io.open(os.path.join(course_path, new_path), 'wb') as f:
                        for chunk in r.iter_content(1024):
                            f.write(chunk)
                    success = True

                except PermissionError:
                    import time
                    time.sleep(1)

            resource.attrs['href'] = new_path

        # Recurse to download new page
        else:
            q = urlparse(url).query
            q_id = re.search(r"id=(\d+)", q)[1]
            q_section = re.search(r"section=(\d+)", q)[1]

            sub_soup = fetch_course(q_id, q_section)
            sub_page_title = save_page(
                sub_soup, subdir=os.path.join(course_title))

            sub_path = os.path.join(
                "resources", sub_page_title, f"{sub_page_title}.html")
            resource.attrs['href'] = sub_path

    print("Downloading inline images...")
    for resource in tqdm(resource_images):

        skip_request = False

        # Fix for url schema
        if resource.get('src').startswith("data:"):
            # Source contains image data, no need to make request
            data = resource.get('src')
            skip_request = True

        elif resource.get('src').startswith("https:") or resource.get('src').startswith("http:"):
            url = resource.get('src')

        else:
            url = "https:" + resource.get('src')

        if not skip_request:
            r = a.s.get(url)

            # Try to get the filename from response headers
            filename = get_filename_from_cd(
                r.headers.get('content-disposition'))

        if skip_request:
            from binascii import a2b_base64

            data_separate = data.split(',')
            binary_data = a2b_base64(data_separate[1])
            ext = re.search(r"image/(\w+);", data_separate[0])[1]

            from uuid import uuid4
            filename = str(uuid4()) + "." + ext

        if filename is None:
            from uuid import uuid4

            # Converts response headers mime type to an extension (may not work with everything)
            ext = r.headers['content-type'].split('/')[-1]
            ext = correct_extension_mimetype(ext)

            filename = str(uuid4()) + "." + ext

        new_path = os.path.join("img", filename)

        # Open the file to write as binary - replace 'wb' with 'w' for text files
        if not os.path.exists(os.path.join(course_path, new_path)):
            with io.open(os.path.join(course_path, new_path), 'wb') as f:

                if not skip_request:
                    for chunk in r.iter_content(1024):
                        f.write(chunk)

                else:
                    f.write(binary_data)

        resource.attrs['src'] = "img/" + filename

    print("Getting remaining resources (CSS, favicon etc)")

    # Download favicon
    icon_link = soup.find("link", rel="shortcut icon")
    r = a.s.get(icon_link['href'])
    path = os.path.join("img", "favicon.ico")
    with io.open(os.path.join(course_path, path), 'wb') as f:
        for chunk in r.iter_content(1024):
            f.write(chunk)

    icon_link['href'] = "img/favicon.ico"

    # Get JS files
    for resource in soup.find_all("script"):
        if resource.attrs.get("src"):
            # if the tag has the attribute 'src'
            url = urljoin(url, resource.attrs.get("src"))

            r = a.s.get(url)

            # Try to get the filename from response headers
            filename = get_filename_from_cd(
                r.headers.get('content-disposition'))

            if filename is None:
                from uuid import uuid4
                filename = str(uuid4()) + ".js"

            new_path = os.path.join("js", filename)

            # Open the file to write as binary - replace 'wb' with 'w' for text files
            if not os.path.exists(os.path.join(course_path, new_path)):
                with io.open(os.path.join(course_path, new_path), 'wb') as f:
                    for chunk in r.iter_content(1024):
                        f.write(chunk)

            resource.attrs['src'] = "js/" + filename

    # Get CSS files
    for resource in soup.find_all("link"):
        if resource.attrs.get("href"):
            # if the link tag has the 'href' attribute
            url = urljoin(url, resource.attrs.get("href"))

            r = a.s.get(url)

            if r.status_code != 200:
                continue

            from uuid import uuid4
            filename = str(uuid4()) + ".css"

            new_path = os.path.join("css", filename)

            # Open the file to write as binary - replace 'wb' with 'w' for text files
            if not os.path.exists(os.path.join(course_path, new_path)):
                with io.open(os.path.join(course_path, new_path), 'wb') as f:
                    for chunk in r.iter_content(1024):
                        f.write(chunk)

            resource.attrs['href'] = "css/" + filename

    save_soup(soup, os.path.join(course_path, f"{course_title}.html"))

    return course_title


def get_filename_from_cd(cd):
    """
    Get filename from content-disposition
    """
    if not cd:
        return None
    fname = re.findall('filename=(.+)', cd)
    if len(fname) == 0:
        return None
    return fname[0].strip('"')


def correct_extension_mimetype(ext):
    """
    Checks for known extension errors
    """
    mimetypes = {
        "msword": "doc",
        "vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "vnd.ms-powerpoint": "ppt",
        "vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
        "vnd.openxmlformats-officedocument.presentationml.slideshow": "pptx",
        "vnd.ms-excel": "xls",
        "vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
        "html; charset=utf-8": "html",
        "x-ms-wmv": "wmv",
        "x-ms-wm": "avi",
        "quicktime": "mov",
        "svg+xml": "svg"
    }

    if ext in mimetypes.keys():
        ext = mimetypes[ext]

    return ext


def save_soup(soup, filename):
    with io.open(filename, 'w', encoding="utf-8") as f:
        f.write(soup.prettify())


if __name__ == "__main__":
    # Login and save cookies to session
    a.login()

    if not isinstance(parameters.course_id, list):
        parameters.course_id = [parameters.course_id]

    # Check that the course does not give an error
    for course in tqdm(parameters.course_id):
        index_soup = fetch_course(course)

        # Parse and save the main course page
        save_page(index_soup)

    print("Complete!")
