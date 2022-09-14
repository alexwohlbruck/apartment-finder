from bs4 import BeautifulSoup
import requests
import json
import datetime
import schedule

AREA = 'south-end-charlotte-nc'
BEDROOMS = 1
MAX_PRICE = 1600
MIN_SQFT = 600
BLACKLIST = [
  'Centro Square',
  'Timber Creek',
  'Arbor Village',
  'Presley Uptown',
  'MAA Reserve',
  'MAA 1225',
  'MAA Gateway',
  'ARIUM FreeMoreWest',
  'Arlo',
  'The Bryant Apartments',
  'The Griff',
  'Gateway West',
]
FAVORITES = []

http = requests.session()
http.headers.update({
  'User-Agent': 'Mozilla/5.0'
})

def build_url():
  return f'https://www.apartments.com/{AREA}/min-{BEDROOMS}-bedrooms-under-{MAX_PRICE}-pet-friendly-cat/'

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
          units_out.append({
            'number': number,
            'price': price,
            'sqft': sqft,
            'available': available,
          })
      
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
      'min_price': min(prices),
      'max_price': max(prices),
      'url': detail_url,
      'images': images,
      'plans': plans_out,
    })
  
  return sorted(results, key=lambda x: (x['name'] not in FAVORITES, x['min_price']))

def scrape_data():
  matches = get_apts()
  max_price = max([x['max_price'] for x in matches])
  min_price = min([x['min_price'] for x in matches])
  average_price = sum([x['average_price'] for x in matches]) / len(matches)
  average_price = round(average_price, 2)

  with open('results.json', 'r+') as f:
    data = json.load(f)

    now = datetime.datetime.now().isoformat()
    data[now] = {
      "max_price": max_price,
      "min_price": min_price,
      "average_price": average_price,
      "apartments": matches,
    }
    
    f.seek(0)
    json.dump(data, f, indent=2)
    f.truncate()
    f.close()
  
if __name__ == '__main__':
  scrape_data()
  schedule.every(4).hours.do(scrape_data)
  while True:
    schedule.run_pending()