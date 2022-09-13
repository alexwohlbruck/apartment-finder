from bs4 import BeautifulSoup
import requests
import json

http = requests.session()
http.headers.update({
  'User-Agent': 'Mozilla/5.0'
})
  

def build_url(query='south-end-charlotte-nc', max_price='1650', bedrooms='1'):
  return f'https://www.apartments.com/{query}/min-{bedrooms}-bedrooms-under-{max_price}-pet-friendly-cat/'

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
  print('Getting apartments list...')
  
  url = build_url()
  
  # Parse the HTML
  soup = get_soup(url)
  apartments = soup.find_all('article', class_='placard')
  
  # Get the data from each list item
  results = []
  for apt in apartments:
    
    detail_anchor = apt.find('a', class_='property-link')
    if not detail_anchor:
      break
    detail_url = detail_anchor['href']
    detail = get_soup(detail_url)
    
    name = detail.find(id='propertyName').text.strip()
    
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
        
        units_out.append({
          'number': number,
          'price': price,
          'sqft': sqft,
          'available': available,
        })
      
      plans_out.append({
        'name': plan_name,
        'units': units_out,
      })
      
    results.append({
      'name': name,
      'address': address,
      'plans': plans_out,
      'images': images,
    })
  
  return results


MAX_PRICE = 1650
MIN_SQFT = 570
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

def find_matches():
  apts = get_apts()
  
  matches = []
  
  for apt in apts:
    for plan in apt['plans']:
      for unit in plan['units']:
        matches_price = unit['price'] <= MAX_PRICE
        matches_sqft = unit['sqft'] >= MIN_SQFT
        not_blacklisted = apt['name'] not in BLACKLIST
        
        if matches_price and matches_sqft and not_blacklisted:
          matches.append({
            'name': apt['name'],
            'address': apt['address'],
            'plan': plan['name'],
            'unit': unit['number'],
            'price': unit['price'],
            'sqft': unit['sqft'],
            'available': unit['available'],
          })
          
  # Sort by favorited then price
  matches = sorted(matches, key=lambda x: (x['name'] not in FAVORITES, x['price']))
          
  return matches

results = json.dumps(find_matches(), indent=2)
# Save to json file
with open('results.json', 'w') as f:
  f.write(results)