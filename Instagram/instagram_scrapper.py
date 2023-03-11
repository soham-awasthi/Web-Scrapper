import os
import csv
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

load_dotenv()

def login_instagram(driver, username, password):
    """
    Logs into Instagram using the provided username and password.
    """
    try:
        wait = WebDriverWait(driver, 15)

        # Navigate to the login page
        driver.get("https://www.instagram.com/accounts/login/")

        # Wait for the username and password fields to appear
        wait.until(EC.presence_of_element_located((By.NAME, "username")))
        wait.until(EC.presence_of_element_located((By.NAME, "password")))

        # Enter credentials
        user_input = driver.find_element(By.NAME, "username")
        pass_input = driver.find_element(By.NAME, "password")
        user_input.send_keys(username)
        pass_input.send_keys(password)

        # Submit the form
        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        login_button.click()

        time.sleep(5)
        pass_elements = driver.find_elements(By.XPATH, "//div[contains(@class, 'xkmlbd1')]")
        print(f"Pass Elements: {pass_elements}")
        
        if pass_elements:
            for pass_element in pass_elements:
                if "Sorry, your password was incorrect. Please double-check your password." in pass_element.text:
                    raise Exception("Invalid credentials provided.")

        # Wait for the homepage to load
        wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'x1q0g3np')]")))

    except Exception as e:
        print(f"Login failed: {e}")
        raise

def scroll_to_load_posts(driver, target_post_count=50):
    """
    Scrolls the page to load more posts dynamically.
    Stops when the target number of posts is loaded or no new posts are found.
    """
    SCROLL_PAUSE_TIME = 5
    last_height = driver.execute_script("return document.body.scrollHeight")
    post_links_set = set()
    
    print(f"Starting to load posts. Target post count: {target_post_count}")
    
    while len(post_links_set) < target_post_count:
        # Scroll to the bottom of the page
        print("Scrolling to the bottom of the page...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE_TIME)
        
        # Find all post links
        print("Searching for post links...")
        post_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/p/')]")
        initial_count = len(post_links_set)
        
        for link in post_links:
            href = link.get_attribute("href")
            if href:
                post_links_set.add(href)
        
        current_count = len(post_links_set)
        print(f"Posts loaded so far: {current_count} (Found {current_count - initial_count} new posts this iteration)")
        
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            print("No more posts to load. Stopping.")
            break
        
        last_height = new_height
    
    print(f"Finished loading posts. Total posts loaded: {len(post_links_set)}")
    if len(post_links_set) < target_post_count:
        print(f"Warning: Only {len(post_links_set)} posts were loaded, which is less than the target of {target_post_count}.")
    
    return list(post_links_set)[:target_post_count]

def scrape_engagement_by_hover(driver, post_urls):
    """
    Scrapes likes and comments by hovering over each post thumbnail.
    Includes a retry mechanism with up to 3 retries per post.
    """
    likes_comments = []
    # wait = WebDriverWait(driver, 10)
    actions = ActionChains(driver)

    for post_url in post_urls:
        retries = 3
        while retries > 0:
            try:
                print(f"Looking for post thumbnail: {post_url}")

                # Locate the post thumbnail by its URL
                post_element = driver.find_element(By.XPATH, f"//a[contains(@href, '/p/{post_url.split('/')[-2]}/')]")
                print(f"Post thumbnail found for {post_url}: {post_element.tag_name}, Visible: {post_element.is_displayed()}")

                # Scroll the element into view and hover
                driver.execute_script("arguments[0].scrollIntoView();", post_element)
                time.sleep(2)
                actions.move_to_element(post_element).perform()
                print(f"Scrolled to and hovered over post: {post_url}")
                time.sleep(2)

                hover_elements = driver.find_elements(By.XPATH, "//span[contains(@class, 'xdj266r')]")
                hover_texts = [elem.text for elem in hover_elements if elem.text.strip()]
                print(f"All hover texts: {hover_texts}")

                # Parse hover texts for likes and comments
                likes, comments = 0, 0
                if len(hover_texts) > 7:
                    likes = convert_to_number(hover_texts[6])
                    comments = convert_to_number(hover_texts[7])

                # Append results and break out of the retry loop
                likes_comments.append({"url": post_url, "likes": likes, "comments": comments})
                print(f"Likes: {likes}, Comments: {comments}")
                break

            except Exception as e:
                retries -= 1
                print(f"Error hovering over post {post_url}. Retries left: {retries}. Error: {e}")
                time.sleep(2)

                if retries == 0:
                    print(f"Failed to process post after multiple retries: {post_url}")
                    likes_comments.append({"url": post_url, "likes": 0, "comments": 0})
                    break

    return likes_comments

def convert_to_number(text):
    try:
        if "k" in text.lower():
            return int(float(text.lower().replace("k", "")) * 1000)
        elif "m" in text.lower():
            return int(float(text.lower().replace("m", "")) * 1000000)
        else:
            return int(text.replace(",", ""))
    except ValueError:
        return 0

def calculate_average_engagement(likes_comments):
    """
    Calculates the average engagement based on likes and comments.
    """
    total_likes = sum(item["likes"] for item in likes_comments)
    total_comments = sum(item["comments"] for item in likes_comments)
    total_posts = len(likes_comments)

    if total_posts == 0:
        return 0

    average_engagement = (total_likes + total_comments) / total_posts
    return average_engagement

def scrape_instagram_user_info(driver, profile_url, target_post_count):
    try:
        # Open the Instagram profile
        print(f"Navigating to profile: {profile_url}")
        driver.get(profile_url)

        # Wait for the profile page to load
        wait = WebDriverWait(driver, 7)
        wait.until(EC.presence_of_element_located((By.XPATH, "//header")))
        print("Profile page loaded.")

        time.sleep(3)
        try:
            priv_element = driver.find_element(By.XPATH, "//div[contains(@class, 'xieb3on')]//span[contains(@class, 'x1lliihq x1plvlek xryxfnj x1n2onr6')]")
 
            # Check if the private profile message is present
            if "This Account is Private".lower() in priv_element.text.lower():
                print(f"Private profile: {profile_url}. Skipping...")
                return None
        except Exception as e:
            # If the element is not found, continue scraping as it's not a private profile
            print(f"No private profile message found for {profile_url}. Continuing...")

        user_info = {}

        # Username
        try:
            print("Extracting username...")
            username_element = driver.find_element(By.XPATH, "//header//h2")
            user_info["user name"] = username_element.text
            print(f"Username: {user_info['user name']}")
        except Exception as e:
            print(f"Error extracting username: {e}")
            user_info["user name"] = "N/A"

        # Profile Image
        try:
            print("Extracting profile image...")
            profile_image_element = wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//img[contains(@alt, 'profile picture')]")
                )
            )
            user_info["user image"] = profile_image_element.get_attribute("src")
            print(f"Profile image: {user_info['user image']}")
        except Exception as e:
            print(f"Error extracting profile image: {e}")
            user_info["user image"] = "N/A"

        # Bio
        try:
            bio_element = driver.find_element(By.XPATH, "//span[contains(@class, '_ap3a _aaco _aacu _aacx _aad7 _aade')]")
            user_info["bio"] = bio_element.text
        except Exception:
            user_info["bio"] = "No bio available"

        # Posts, Followers, Following
        try:
            print("Extracting stats (posts, followers, following)...")
            stats_elements = driver.find_elements(By.XPATH, "//header//ul/li")
            user_info["number of posts"] = stats_elements[0].text.split(" ")[0]
            user_info["number of followers"] = stats_elements[1].text.split(" ")[0]
            user_info["number of following"] = stats_elements[2].text.split(" ")[0]
            print(f"Stats - Posts: {user_info['number of posts']}, Followers: {user_info['number of followers']}, Following: {user_info['number of following']}")
        except Exception as e:
            print(f"Error extracting stats: {e}")
            user_info["number of posts"] = "N/A"
            user_info["number of followers"] = "N/A"
            user_info["number of following"] = "N/A"

        # Last 50 Posts
        posts = []
        try:
            print("Scrolling to load posts...")
            time.sleep(3)
            print(f"target posts: {target_post_count}")
            posts = scroll_to_load_posts(driver, target_post_count)

            print(f"Total Posts Loaded: {len(posts)}")
            print(f"Last 50 Posts: {posts}")
        except Exception as e:
            print(f"Error while extracting posts: {e}")
            posts = []

        user_info["last 50 posts"] = posts

        # Scrape engagement details using hover
        print("Scraping engagement details using hover...")
        likes_comments = scrape_engagement_by_hover(driver, posts)

        # Calculate average engagement
        average_engagement = calculate_average_engagement(likes_comments)
        user_info["average engagement"] = round(average_engagement, 2)
        print(f"Average Engagement: {user_info['average engagement']}")

        return user_info

    except Exception as e:
        print(f"Error during scraping: {e}")
        return None

def save_to_csv(data, output_file="instagram_data.csv"):
    """
    Saves the scraped data to a CSV file.
    """
    if not data:
        print("No data to save.")
        return

    keys = data[0].keys()
    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=keys)
        writer.writeheader()
        writer.writerows(data)

def configure_driver():
    options = Options()
    
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--start-maximized")
    options.add_argument("--lang=en-US")
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option("useAutomationExtension", False)
    
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    
    # Mask WebDriver signature
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        window.chrome = { runtime: {} };
        """
    })
    
    return driver

if __name__ == "__main__":
    # Provide your username/password in a .env file or enter below.
    insta_email = os.getenv("INSTAGRAM_USERNAME") or ""
    insta_password = os.getenv("INSTAGRAM_PASSWORD") or ""
    target_post_count = int(os.getenv("TARGET_POST_COUNT") or 50)

    profile_urls = [
        "https://www.instagram.com/dualipa/",
    ] # add more profile urls to scrap

    driver = configure_driver()

    try:
        print("Logging in...")
        if insta_email and insta_password:
            login_instagram(driver, insta_email, insta_password)
        else:
            raise Exception("Invalid credentials provided.")
            
        time.sleep(5)

        all_user_data = []
        for url in profile_urls:
            print(f"Scraping: {url}")
            user_data = scrape_instagram_user_info(driver, url, target_post_count)
            if user_data:
                all_user_data.append(user_data)
            time.sleep(5)

        if all_user_data:
            save_to_csv(all_user_data)
            print("Data saved to 'instagram_data.csv'")
        else:
            print("No data scraped.")

    finally:
        driver.quit()

