import requests
import json
from html.parser import HTMLParser


prod_id = '<replace with product id>'
link = f'<replace with link>{id}'


class PSParser(HTMLParser):
    args_key = 'args'
    cache_key = 'cache'
    product_id_key = 'productId'
    product_key = f'Product:{prod_id}'
    price_key = 'price'
    web_ctas_key = 'webctas'
    platforms_key = 'platforms'
    refs_key = '__ref'
    name_key = 'name'
    base_price_key = 'basePrice'
    discount_key = 'discountedPrice'
    discount_percent_key = 'discountText'
    service_key = 'serviceBranding'
    empty_service = []
    plus_service = 'PS_PLUS'
    cta_ids = []
    is_ld_json = False
    is_app_json = False
    found_price = False

    def find_cta_key(self, cache_data):
        if self.product_key in cache_data:
            product = cache_data[self.product_key]
            if self.web_ctas_key in product:
                for cta in product[self.web_ctas_key]:
                    if self.refs_key in cta:
                        self.cta_ids.append(cta[self.refs_key])

    def find_platforms(self, cache_data):
        if self.product_key in cache_data:
            product = cache_data[self.product_key]
            if self.platforms_key in product:
                print(product[self.platforms_key])

    def error(self, message):
        print(f"Error: {message}")

    def handle_starttag(self, tag, attrs):
        self.is_ld_json = tag == 'script' and ('type', 'application/ld+json') in attrs
        self.is_app_json = tag == 'script' and ('type', 'application/json') in attrs

    def handle_endtag(self, tag):
        self.is_ld_json = False
        self.is_app_json = False

    def handle_data(self, data):
        if self.found_price:
            return
        if self.is_ld_json:
            main_data = json.loads(data)
            print(f"script tag data:")
            print(f"Name: {main_data['name']}")
            print(f"Category: {main_data['category']}")
            print(f"Description: {main_data['description']}")
            print(f"Image Link: {main_data['image']}")
        if self.is_app_json:
            json_data = json.loads(data)
            if self.cache_key in json_data:
                cache = json_data[self.cache_key]
                self.find_cta_key(cache)
                self.find_platforms(cache)
                for cta_id in self.cta_ids:
                    if cta_id and cta_id in cache:
                        game = cache[cta_id]
                        if self.price_key in game:
                            # print(game[self.price_key])
                            price_data = game[self.price_key]
                            if not self.found_price:
                                print(f"Base Price: {price_data['basePrice']}")
                            discount = price_data['discountedPrice']
                            percent = price_data['discountText']
                            service = ' - w/ PLUS' if 'PS_PLUS' in price_data['serviceBranding'] else ''
                            print(f"Discount: {discount} ({percent}){service}")
                            if discount == "Gratuito":
                                print(price_data)
                            self.found_price = True


r = requests.get(link)

# print(r.text)

parser = PSParser()
parser.feed(r.text)
