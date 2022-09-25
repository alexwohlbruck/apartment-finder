from bs4 import BeautifulSoup
import requests
import json
import datetime
import schedule
import webbrowser
import requests
import dotenv
import os
from time import sleep

dotenv.load_dotenv()

AREA = os.getenv('AREA')
BEDROOMS = int(os.getenv('BEDROOMS'))
MAX_PRICE = int(os.getenv('MAX_PRICE'))
MIN_SQFT = int(os.getenv('MIN_SQFT'))
BLACKLIST = os.getenv('BLACKLIST').split(',')
FAVORITES = os.getenv('FAVORITES').split(',')

http = requests.session()
http.headers.update({
  'User-Agent': 'Mozilla/5.0'
})

def build_url():
  return f'https://www.apartments.com/{AREA}/min-{BEDROOMS}-bedrooms-under-{MAX_PRICE}-pet-friendly-cat/'

def build_unique_key(apt, unit):
  s = f'{apt}-{unit}'
  s = s.lower().replace(' ', '-')
  return s
    
def get_soup(url):
  r = http.get(url)
  r.raise_for_status()
  r.encoding = 'utf-8'
  html = r.text
  return BeautifulSoup(html, 'html.parser')

def get_text(soup, tag, class_):
  el = soup.find(tag, class_=class_)
  if not el:
    return None
  # Remove all children elements with class screenReaderOnly
  for child in el.find_all(class_='screenReaderOnly'):
    child.decompose()
  
  if el:
    return el.text.strip()
  return None

def send_message(name, number, price, sqft, available, url):
  try:
    print('Sending message for', name, number)
    message = f'New apartment available at {name}! {number} is available for ${price} ({sqft} sqft) and is available {available}. See more at {url}'
    print(message)

    request_url = "https://u7fsepk6od5wfke1whpgl6vfdj3kbmyp.ui.nabu.casa/api/services/notify/mobile_app_pixel_6_pro"
    headers = {
        "Authorization": f"Bearer {os.getenv('HA_TOKEN')}",
        "content-type": "application/json",
    }
    body = {
      "message": message,
      "title": "New Apartment Available!",
      # Tap action open url in chrome
      "data": {
        "actions": [
          {
            "action": "URI",
            "title": "View listing",
            "uri": url, 
          } 
        ]
      },
    }
    r = requests.post(request_url, headers=headers, json=body)
    print(r.text)
    sleep(0.5)
  except Exception as e:
    print(e)

# Scrape apartments.com for apartments
def get_apts():
  print('Fetching apartments list...')
  
  url = build_url()
  
  # Parse the HTML
  soup = get_soup(url)
  apartments = soup.find_all('article', class_='placard')
  
  print(f'Fetched {len(apartments)} apartments')
  
  # Get the data from each list item
  results = []
  for apt in apartments:
    
    try:
      with open('results.json', 'r') as f:
        existing_keys = json.load(f)['keys']
        f.close()
      
      detail_anchor = apt.find('a', class_='property-link')
      if not detail_anchor:
        break
      detail_url = detail_anchor['href']
      detail = get_soup(detail_url)
      
      name = detail.find(id='propertyName').text.strip()
      prices = []
      
      if name in BLACKLIST:
        continue
      
      print('Fetched details for', name)
      
      address = get_text(apt, 'div', 'property-address')
      carousel = detail.find('div', class_='carouselContent')
      images = carousel.find_all('li', class_='item')
      images = [img.find('img')['src'] for img in images]
      
      one_beds = detail.find('div', attrs={'data-tab-content-id': 'bed1'})
      plans = one_beds.find_all('div', class_='pricingGridItem')
      plans_out = []
      
      for plan in plans:
        plan_name = get_text(plan, 'span', 'modelName')
        
        units = plan.find_all('li', class_='unitContainer')
        units_out = []
        
        for unit in units:
          number = get_text(unit, 'div', 'unitColumn column')
          price = get_text(unit, 'div', 'pricingColumn column')
          try:
            price = int(price.replace('$', '').replace(',', ''))
          except:
            price = -1
          sqft = int(get_text(unit, 'div', 'sqftColumn column').replace(',', ''))
          available = get_text(unit, 'span', 'dateAvailable')
          
          if (sqft >= MIN_SQFT and price <= MAX_PRICE):
            prices.append(price)
            unit_data = {
              'number': number,
              'price': price,
              'sqft': sqft,
              'available': available,
            }
            units_out.append(unit_data)
            units_out.sort(key=lambda x: x['price'])
            if (build_unique_key(name, number) not in existing_keys):
              send_message(name, number, price, sqft, available, detail_url)
          
        
        if len(units_out) == 0:
          continue
          
        plans_out.append({
          'name': plan_name,
          'units': units_out,
        })
      
      if len(prices) == 0:
        continue
      
      results.append({
        'name': name,
        'address': address,
        'average_price': round(sum(prices) / len(prices), 2),
        'median_price': round(sorted(prices)[len(prices) // 2], 2),
        'min_price': min(prices),
        'max_price': max(prices),
        'url': detail_url,
        'images': images,
        'plans': plans_out,
      })
    except Exception as e:
      print(e)
    
  return sorted(results, key=lambda x: (x['name'] not in FAVORITES, x['min_price']))

def scrape_data():
  matches = get_apts()
  max_price = max([x['max_price'] for x in matches])
  min_price = min([x['min_price'] for x in matches])
  average_price = sum([x['average_price'] for x in matches]) / len(matches)
  average_price = round(average_price, 2)
  median_price = sorted([x['median_price'] for x in matches])[len(matches) // 2]

  with open('results.json', 'r+') as f:
    data = json.load(f)
    
    # Build list of keys for all units
    keys = []
    for apt in matches:
      for plan in apt['plans']:
        for unit in plan['units']:
          keys.append(build_unique_key(apt['name'], unit['number']))

    now = datetime.datetime.now().isoformat()
    data['snapshots'][now] = {
      "max_price": max_price,
      "min_price": min_price,
      "average_price": average_price,
      "median_price": median_price,
      "apartments": matches,
    }
    data['keys'] =  list(set(keys))
    
    f.seek(0)
    json.dump(data, f, indent=2)
    f.truncate()
    f.close()
  
if __name__ == '__main__':
  scrape_data()
  # webbrowser.open('http://127.0.0.1:5500/index.html')
  # schedule.every(4).hours.do(scrape_data)
  # while True:
  #   schedule.run_pending()