import json
from playwright.sync_api import sync_playwright

def normalize_text(text):
    """Like XPath normalize-space()"""
    return ' '.join(text.split())

def get_xpath_or_fallback(element, page):
    """Return XPath + whether its ID is stable"""

    # Generate absolute XPath
    xpath = element.evaluate("""
    function(node) {
        if (node.id) {
            return '//*[@id="' + node.id + '"]';
        }
        let path = '';
        while(node && node.nodeType === Node.ELEMENT_NODE) {
            let index = 1;
            let sibling = node.previousElementSibling;
            while(sibling) {
                if (sibling.nodeName === node.nodeName) {
                    index++;
                }
                sibling = sibling.previousElementSibling;
            }
            let tagName = node.nodeName.toLowerCase();
            path = '/' + tagName + '[' + index + ']' + path;
            node = node.parentNode;
        }
        return '/' + path;
    }
    """)

    # If XPath uses an ID, check if it still matches in final DOM
    is_id_stable = True
    if "@" in xpath and "id=" in xpath:
        locator = page.locator(f"xpath={xpath}")
        if locator.count() == 0:
            is_id_stable = False

    return xpath, is_id_stable

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        url = "https://magicspoon.com/collections/shop-all"

        # Load with fallback
        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
        except:
            page.goto(url, wait_until="load", timeout=30000)

        # Accept cookie banner
        try:
            page.wait_for_selector("button", timeout=5000)
            cookie_accept = page.get_by_role("button", name="Accept")
            if cookie_accept.is_visible():
                cookie_accept.click()
                print("Cookie consent accepted")
        except:
            print(" No cookie banner found")

        page.wait_for_selector("body")

        elements = page.query_selector_all("a[href], button")
        output = []
        pom_entries = []

        for element in elements:
            if not element.is_visible():
                continue
            if element.bounding_box() is None:
                continue

            tag = element.evaluate('e => e.tagName.toLowerCase()')
            href = element.get_attribute('href')
            raw_text = element.inner_text().strip()
            text = normalize_text(raw_text)

            xpath, is_id_stable = get_xpath_or_fallback(element, page)

            # CSS locator fallback
            css_locator = None
            if tag == 'a' and href:
                css_locator = f'page.locator(\'a[href="{href}"]\')'
            elif tag == 'button':
                css_locator = 'page.locator("button")'

            # Fallback
            better_selector = None
            if not is_id_stable or page.locator(f"xpath={xpath}").count() == 0:
                if tag == 'a' and href:
                    better_selector = f'page.locator(\'a[href="{href}"]\')'
                elif text:
                    better_selector = f'page.get_by_text("{text}")'

            name = f"{tag.upper()}: {text}" if text else f"{tag.upper()} element"
            output.append({
                "name": name,
                "tag": tag,
                "href": href,
                "text": text,
                "xpath": xpath,
                "id_stable": is_id_stable,
                "better_selector": better_selector,
                "css_locator": css_locator
            })

            pom_locator = None
            if is_id_stable:
                pom_locator = f'self._{tag}_{text.lower().replace(" ", "_")} = page.locator(\'xpath={xpath}\')'
            elif better_selector:
                pom_locator = f'self._{tag}_{text.lower().replace(" ", "_")} = {better_selector}'
            elif css_locator:
                pom_locator = f'self._{tag}_{text.lower().replace(" ", "_")} = {css_locator}'

            if pom_locator:
                pom_entries.append(pom_locator)

        with open('locators_validated.json', 'w') as f:
            json.dump(output, f, indent=2)

        with open('generated_page.py', 'w') as f:
            f.write("class GeneratedPage:\n")
            f.write("    def __init__(self, page):\n")
            for entry in pom_entries:
                f.write(f"        {entry}\n")

        print("Saved: locators_validated.json and generated_page.py")

        browser.close()

if __name__ == "__main__":
    main()
