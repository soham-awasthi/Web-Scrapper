import time
import json
import random
import os
from dotenv import load_dotenv
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import NoSuchElementException
import re

load_dotenv()

discord_email = os.getenv("DISCORD_EMAIL")
discord_password = os.getenv("DISCORD_PASSWORD")

data = []

def log(message):
    """Enhanced logging function with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def configure_driver():
    log("Initializing Chrome driver with anti-detection settings")
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
    
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        window.chrome = { runtime: {} };
        """
    })
    
    log("Driver configured successfully")
    return driver

def login_discord(driver, email, password):
    """Universal login handler with domain support"""
    login_url = 'https://canary.discord.com/login'
    
    try:
        wait = WebDriverWait(driver, 10)
        driver.get(login_url)
        
        log("Entering credentials")
        email_field = WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.NAME, "email"))
        )
        ActionChains(driver).send_keys_to_element(email_field, email).pause(0.5).perform()
        
        password_field = driver.find_element(By.NAME, "password")
        ActionChains(driver).send_keys_to_element(password_field, password).pause(0.5).perform()

        log("Submitting login form")
        login_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))
        )
        driver.execute_script("arguments[0].click();", login_button)

        log("Verifying login success")

        time.sleep(2)
        wait.until(lambda d: 'channels/@me' in d.current_url)
        
        log("Login fully verified")
        return True

    except Exception as e:
        driver.save_screenshot("login_failure.png")
        log(f"Login failed: {str(e)}")
        raise
    
def extract_server_id(server_url):
    """Extract server ID from the server URL."""
    return server_url.split("/")[-1]

def partial_scroll(driver, scroll_container, fraction=0.25):
    """
    Scroll the container incrementally by 'fraction' of its visible height.
    This helps reveal intermediate items in Discord's virtual list,
    so that group headers or new Online members aren't skipped.
    """
    current_pos = driver.execute_script("return arguments[0].scrollTop", scroll_container)
    viewport_height = driver.execute_script("return arguments[0].clientHeight", scroll_container)
    new_pos = current_pos + (viewport_height * fraction)

    driver.execute_script(f"arguments[0].scrollTop = {new_pos}", scroll_container)
    time.sleep(2)

def extract_groups_and_online_members(driver, server_id, target_group="Online"):
    """
    1) Clicks the 'Show Member List'.
    2) Finds the scrollable container (the 'scrollerBase_*' div).
    3) Continuously partial-scrolls to find all group headers:
       - For each group header:
         * Extract and store (group_name, count_from_header).
         * If group_name == target_group (e.g., "Online"), extract all usernames.
    4) Stops when multiple scrolls yield no new group headers or no new Online members.
    5) Returns a structure with:
         - A list of all groups (name + total count from header).
         - A list of all members in the 'Online' group.
    """

    log("Extracting group counts + online members...")

    try:
        member_list_btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//div[contains(@aria-label, 'Show Member List')]")
            )
        )
        member_list_btn.click()
        log("Clicked the 'Show Member List' button.")
    except TimeoutException:
        log("Could not find/click the 'Show Member List' button within 15s.")
        raise
    except Exception as e:
        log(f"Error clicking 'Show Member List': {e}")
        raise

    scroll_container = None
    try:
        container_selector = f'div[data-list-id="members-{server_id}"]'
        container = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, container_selector))
        )
        scroll_container = container
        log("Located the scrollable container.")
    except TimeoutException:
        log("Failed to locate the scrollable container in time.")
        raise
    except Exception as e:
        log(f"Error finding scrollable container: {e}")
        raise

    group_counts = {} 
    online_members = {}
    scroll_attempts = 0
    max_attempts = 20

    while scroll_attempts < max_attempts:
        log(f"\n=== Scroll attempt {scroll_attempts + 1}/{max_attempts} ===")
        partial_scroll(driver, scroll_container, fraction=0.25)

        try:
            group_headers = scroll_container.find_elements(By.XPATH, ".//h3[contains(@class, 'membersGroup_')]")
        except StaleElementReferenceException:
            try:
                container = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, container_selector))
                )
                scroll_container = container.find_element(By.CSS_SELECTOR, "div[class*='scrollerBase_']")
                group_headers = scroll_container.find_elements(By.XPATH, ".//h3[contains(@class, 'membersGroup_')]")
            except Exception as e:
                log(f"Error re-locating group headers: {e}")
                break

        log(f"Found {len(group_headers)} group headers in DOM this pass.")

        newly_discovered_online_members = 0
        newly_discovered_groups = 0

        for group_header in group_headers:
            try:
                # Extract text from the group header (e.g., "Online — 12 members")
                group_text = driver.execute_script(
                    "return arguments[0].textContent.replace(/\\s+/g, ' ').trim();",
                    group_header
                )
                match = re.match(r"^(.*?)\s*[,—\-]\s*(\d+)\s+members?(.*)$", group_text)
                if not match:
                    log(f"⚠️ Couldn't parse group header: {group_text}")
                    continue

                group_name = match.group(1).strip()
                group_count = int(match.group(2))

                if (group_name not in group_counts) or (group_counts[group_name] != group_count):
                    group_counts[group_name] = group_count
                    newly_discovered_groups += 1
                    log(f"Discovered/updated group '{group_name}' => {group_count} members (header).")

                if group_name == target_group:
                    script = """
                    var group = arguments[0];
                    var members = [];
                    var next = group.nextElementSibling;
                    while (next) {
                        if (next.matches('h3')) break;
                        if (next.matches('div[class*="member_"]')) {
                            members.push(next);
                        }
                        next = next.nextElementSibling;
                    }
                    return members;
                    """
                    member_divs = driver.execute_script(script, group_header)

                    for idx, div_el in enumerate(member_divs):
                        try:
                            member_id = div_el.get_attribute("data-list-item-id") or f"temp_{group_name}_{idx}"
                            if member_id not in online_members:
                                if not div_el.is_displayed():
                                    continue

                                username_el = div_el.find_element(By.XPATH, ".//span[contains(@class, 'username')]")
                                username = username_el.text.strip()
                                online_members[member_id] = {
                                    "username": username,
                                    "group": group_name
                                }
                                newly_discovered_online_members += 1
                        except Exception as ex:
                            log(f"Error extracting a {target_group} member: {ex}")

            except Exception as e:
                log(f"🚨 Group header processing error: {e}")

        total_groups_now = len(group_counts)
        total_online_now = len(online_members)

        if newly_discovered_groups > 0 or newly_discovered_online_members > 0:
            scroll_attempts = 0
            log(f"✅ Found new data: +{newly_discovered_groups} groups, +{newly_discovered_online_members} online members.")
        else:
            scroll_attempts += 1
            log(f"🚩 No new data discovered; scroll_attempts = {scroll_attempts}.")

        log(f"Current total: {total_groups_now} groups known, {total_online_now} online members extracted.")

    groups_list = []
    for gname, gcount in group_counts.items():
        groups_list.append({
            "group": gname,
            "count": gcount
        })

    online_list = []
    for m_id, info in online_members.items():
        online_list.append({
            "id": m_id,
            "username": info["username"]
        })

    final_data = {
        "groups": groups_list,
        "online_members": online_list
    }

    log(f"Done. Found {len(groups_list)} groups total. Extracted {len(online_list)} '{target_group}' members.")
    return final_data

def scrape_server_data(driver, server_url, username, password, channel_urls=[]):
    try:
        # Login
        log("Logging into Discord")
        login_discord(driver, username, password)

        log(f"Accessing server: {server_url}")
        driver.get(server_url)

        server_info = {
            "server_name": "",
            "server_id": extract_server_id(server_url),
            "channels": [],
            "members": {},
            "messages": [],
            "last_active": ""
        }

        time.sleep(7)
        log("Scraping server data")
        # Extract server name
        server_id = str(server_info['server_id'])

        # Find the div with matching id, then locate h3 inside it
        xpath = f"//div[contains(@id, 'chat-messages-{server_id}')]//h3"

        log("Extracting server name")
        log(f"Xpath: {xpath}")

        # Wait for the h3 element inside the identified div
        element = WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.XPATH, xpath))
        )

        full_text = element.text.strip()

        # Extract the last part after splitting by newline
        server_info["server_name"] = full_text.split("\n")[-1].strip()
        
        log(f"Server name: {server_info['server_name']}")

        # Extract channels
        log("Extracting channels")
        xpath = f"//nav[contains(@aria-label, '{server_info['server_name']} (server)')]"

        log(f"Xpath: {xpath}")
        main_container = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, xpath)))

        all_items = main_container.find_elements(By.XPATH, ".//ul[@aria-label='Channels']//li[@data-dnd-name]")

        server_info["channels"] = []
        current_category = None
        category_channels = []

        log(f"Found {len(all_items)} items")
        for item in all_items:
            if item.get_attribute("draggable") == "true":
                if current_category and category_channels:
                        server_info["channels"].append({
                            "category": current_category,
                            "channels": category_channels
                        })

                current_category = item.get_attribute("data-dnd-name")
                category_channels = []

            else:
                channel_name = item.get_attribute("data-dnd-name")
                channel_url = item.find_element(By.XPATH, ".//a").get_attribute("href")
                channel_id = item.find_element(By.XPATH, ".//a").get_attribute("data-list-item-id") or channel_name

                channel_type = "voice" if "voice" in current_category.lower() else "text"

                category_channels.append({
                    "name": channel_name,
                    "id": channel_id,
                    "url": channel_url,
                    "type": channel_type
                })

            log(f"server_info['channels']: {server_info['channels']}")

        log(f"Extracted {len(server_info['channels'])} channels")

        # Extract members
        log("Extracting channel members...")

        result = extract_groups_and_online_members(driver, server_id, target_group="member")
        log(f"Final result:\n{result}")

        server_info["members"] = result

        log("Server Info: {}".format(server_info))

    except Exception as e:
        print(f"Scraping failed: {str(e)}")
        return None
    
    server_info["last_active"] = extract_last_active(driver, server_info["server_id"])

    log("Extracting messages...")
    updated_info = extract_messages(driver, server_info, channel_urls)
    print(f"Updated info: {updated_info}")
    if updated_info:
        log("Final extracted data:")
        for idx, msg in enumerate(updated_info["messages"], start=1):
            log(f"{idx}) [{msg['timestamp']}] {msg['username']}: {msg['content']} (Attachments: {msg['attachments']})")

    return updated_info

def extract_messages(driver, server_info, channel_urls):
    """
    Extract username, message content, timestamp, and attachments
    from each channel in channel_urls.
    Updates server_info['messages'] with a list of message dicts:
       {
         "username": "...",
         "timestamp": "...",
         "content": "...",
         "attachments": [...]
       }
    """
    if not channel_urls:
        return []

    if "messages" not in server_info:
        server_info["messages"] = []

    for channel_url in channel_urls:
        try:
            driver.get(channel_url)
            # Allow Discord to load
            time.sleep(5)

            try:
                # 1) Wait for <ol data-list-id="chat-messages"> to appear
                ol_element = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "ol[data-list-id='chat-messages']")
                    )
                )
                log("Located the <ol data-list-id='chat-messages'> element.")
            except TimeoutException:
                log(f"Timed out waiting for chat-messages <ol> in {channel_url}.")
                continue

            # 2) Scroll to bottom to see the newest messages
            driver.execute_script(
                "arguments[0].scrollTop = arguments[0].scrollHeight",
                ol_element
            )
            time.sleep(2)

            # 3) Find all <li> with id starting "chat-messages-"
            message_elements = ol_element.find_elements(
                By.CSS_SELECTOR,
                "li[id^='chat-messages-']"
            )
            log(f"Found {len(message_elements)} message <li> elements in {channel_url}.")

            # 4) Parse each message
            for msg_el in message_elements:
                try:
                    username = "Unknown"
                    timestamp = "Unknown"
                    content = ""
                    attachments = []

                    # --- Extract Username (Two-step fallback) ---
                    try:
                        username_el = msg_el.find_element(
                            By.CSS_SELECTOR,
                            "span[id^='message-username-'], span[class*='username_']"
                        )
                        username = username_el.text.strip()
                    except NoSuchElementException:
                        try:
                            heading_el = msg_el.find_element(By.CSS_SELECTOR, "h3[class*='header_']")
                            possible_user_el = heading_el.find_element(By.CSS_SELECTOR, "span[class*='username_']")
                            username = possible_user_el.text.strip()
                        except NoSuchElementException:
                            pass

                    # --- Extract Timestamp ---
                    # We try .datetime first, then fallback to .aria-label
                    try:
                        time_el = msg_el.find_element(By.CSS_SELECTOR, "time")
                        datetime_attr = time_el.get_attribute("datetime")
                        aria_label = time_el.get_attribute("aria-label")

                        # If the <time> tag doesn't have datetime, use aria-label
                        if datetime_attr:
                            timestamp = datetime_attr
                        elif aria_label:
                            timestamp = aria_label
                        else:
                            timestamp = "Unknown"
                    except NoSuchElementException:
                        pass

                    # --- Extract Content ---
                    try:
                        content_el = msg_el.find_element(
                            By.CSS_SELECTOR,
                            "div[id^='message-content.'], div[class*='messageContent_']"
                        )
                        content = content_el.text.strip()
                    except NoSuchElementException:
                        pass

                    image_els = msg_el.find_elements(By.CSS_SELECTOR, "img")
                    for img_el in image_els:
                        src = img_el.get_attribute("src")
                        if src and "cdn.discordapp.com" in src:
                            attachments.append(src)

                    server_info["messages"].append({
                        "username": username,
                        "timestamp": timestamp,
                        "content": content,
                        "attachments": attachments
                    })

                except Exception as ex:
                    log(f"Skipping one message due to error: {ex}")

        except Exception as e:
            log(f"Error extracting messages from {channel_url}: {e}")

    return server_info

def extract_last_active(driver, server_id, previous_last_active={}):
    """
    Extracts last active times for all users, including offline members.
    Uses incremental scrolling with DOM tracking to ensure full coverage.
    """
    log("Extracting last active times for all members...")
    last_active = previous_last_active.copy()
    scroll_attempts = 0
    max_scroll_attempts = 15
    last_count = 0
    unique_member_ids = set()

    try:
        # Locate member list container
        container_selector = f'div[data-list-id="members-{server_id}"]'
        scroll_container = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, container_selector))
        )
    except Exception as e:
        log(f"Member list container error: {e}")
        return last_active

    while scroll_attempts < max_scroll_attempts:
        try:
            members = WebDriverWait(scroll_container, 10).until(
                EC.presence_of_all_elements_located(
                    (By.XPATH, ".//div[contains(@class, 'member_') and @data-list-item-id]")
                )
            )
            current_count = len(members)
            
            for member in members:
                try:
                    member_id = member.get_attribute("data-list-item-id")
                    if member_id in unique_member_ids:
                        continue
                        
                    unique_member_ids.add(member_id)
                    
                    username = member.find_element(
                        By.XPATH, ".//span[contains(@class, 'username')]"
                    ).text.strip()

                    status_classes = member.get_attribute("class")
                    if "online" in status_classes:
                        status = "online"
                    elif "idle" in status_classes:
                        status = "idle"
                    elif "dnd" in status_classes:
                        status = "dnd"
                    else:
                        status = "offline"

                    if (member_id not in last_active) or (last_active[member_id].get("status") != status):
                        last_active[member_id] = {
                            "username": username,
                            "status": status,
                            "last_seen": datetime.utcnow().isoformat()
                        }

                except Exception as e:
                    log(f"Skipping member processing: {e}")

            if current_count == last_count:
                scroll_attempts += 1
                log(f"No new members ({scroll_attempts}/{max_scroll_attempts})")
            else:
                scroll_attempts = 0
                last_count = current_count

            driver.execute_script(
                "arguments[0].scrollTop += arguments[0].clientHeight * 0.25", 
                scroll_container
            )
            time.sleep(1.5)

        except StaleElementReferenceException:
            log("DOM updated, refreshing elements...")
            scroll_container = driver.find_element(By.CSS_SELECTOR, container_selector)
            
        except Exception as e:
            log(f"Scroll iteration error: {e}")
            break

    log(f"Processed {len(unique_member_ids)} members with {scroll_attempts} stale scrolls")
    return last_active

def save_to_file(data, filename="discord_data.json"):
    with open(filename, "w") as file:
        json.dump(data, file, indent=4)
    print(f"Data saved to {filename}")

if __name__ == "__main__":
    # Provide your credentials here
    EMAIL = discord_email
    PASSWORD = discord_password
    
    server_urls = [
        "",
    ]

    channel_urls = [
        "",
    ]

    driver = configure_driver()
    try:
        for server_url in server_urls:
            
            server_data = scrape_server_data(driver, server_url, EMAIL, PASSWORD, channel_urls)
            if server_data:
                data.append(server_data)
            
            time.sleep(random.uniform(3, 7))
        
        print("All server data extracted successfully")
        print(data)
        save_to_file(data)
        
    finally:
        driver.quit()

