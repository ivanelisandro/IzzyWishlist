from django.conf import settings
from django.views.generic.base import TemplateView
from html.parser import HTMLParser
import json
import operator
import requests
import threading


class PSView(TemplateView):
    template_name = 'playsapp/index.html'

    def __init__(self):
        super().__init__()
        self.wish = WishList()
        self.wish.load()
        self.wish.fill_list()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sorted_games = sorted(self.wish.games, key=operator.attrgetter('name'))
        games = [game.to_dict() for game in sorted_games]
        context['games'] = games
        return context


class WishList:
    def __init__(self):
        self.links = []
        self.games = []

    def load(self):
        self.links = []
        with open(settings.PLAYSAPP_LINKS_PATH, encoding='utf-8') as file:
            for line in file.read().splitlines():
                if line:
                    self.links.append(line)

    def fill_list(self):
        if len(self.games) > 0:
            return

        self.games = []
        tasks = []
        for link in self.links:
            thread = threading.Thread(target=self.load_game, args=(link,))
            thread.start()
            tasks.append(thread)
        for t in tasks:
            t.join()

    def load_game(self, link):
        game = GameInfo(link)
        browser = PSBrowser(game)
        content = browser.retrieve_info()
        parser = PSParser(game)
        parser.feed(content)
        self.games.append(game)


class GameInfo:
    def __init__(self, link):
        self.link = link
        self.product_id = link.rstrip("/").split("/")[-1]
        self.name = ''
        self.category = ''
        self.description = ''
        self.image_link = ''
        self.base_price = ''
        self.discounted_price = ''
        self.discount_percent = ''
        self.plus_discount = ''
        self.plus_percent = ''

    def format_discount(self):
        _base_discount = None
        if self.discounted_price and self.discounted_price != self.base_price:
            _base_discount = f'{self.discounted_price} ({self.discount_percent})'
        if self.plus_discount and self.plus_discount != self.base_price:
            if _base_discount:
                _base_discount += " // "
            _base_discount = f'{self.plus_discount} ({self.plus_percent}) w/ Plus'

        return _base_discount

    def to_dict(self):
        return {
            'product_id': self.product_id,
            'link': self.link,
            'image_link': f"{self.image_link}?w=150",
            'name': self.name,
            'category': self.category,
            'base_price': self.base_price,
            'discounted_price': self.format_discount(),
        }


class LdJson:
    attr = ('type', 'application/ld+json')
    name = 'name'
    category = 'category'
    description = 'description'
    image = 'image'


class AppJson:
    attr = ('type', 'application/json')
    args = 'args'
    cache = 'cache'
    product_id = 'productId'
    product = f'Product:'
    price = 'price'
    web_ctas = 'webctas'
    refs = '__ref'
    name = 'name'
    base_price = 'basePrice'
    upsell = 'upsellText'
    upsell_evaluation = 'Avaliação'
    discount = 'discountedPrice'
    discount_percent = 'discountText'
    service = 'serviceBranding'
    empty_service = []
    plus_service = 'PS_PLUS'


class PSParser(HTMLParser):
    cta_ids = []
    script_tag = 'script'
    is_ld_json = False
    is_app_json = False
    found_price = False

    def __init__(self, game: GameInfo):
        super().__init__()
        self.game = game
        self.found_price = False

    def find_cta_keys(self, cache_data):
        product_key = AppJson.product + self.game.product_id
        if product_key in cache_data:
            product = cache_data[product_key]
            if AppJson.web_ctas in product:
                for cta in product[AppJson.web_ctas]:
                    if AppJson.refs in cta:
                        self.cta_ids.append(cta[AppJson.refs])

    def error(self, message):
        print(f"Error: {message}")

    def handle_starttag(self, tag, attrs):
        self.is_ld_json = tag == self.script_tag and LdJson.attr in attrs
        self.is_app_json = tag == self.script_tag and AppJson.attr in attrs

    def handle_endtag(self, tag):
        self.is_ld_json = False
        self.is_app_json = False

    def handle_data(self, data):
        if self.found_price:
            return
        if self.is_ld_json:
            self.set_main_data(data)
        if self.is_app_json:
            json_data = json.loads(data)
            if AppJson.cache in json_data:
                cache = json_data[AppJson.cache]
                self.find_cta_keys(cache)
                self.set_price_data(cache)

    def set_main_data(self, data):
        main_data = json.loads(data)
        self.game.name = main_data[LdJson.name]
        self.game.category = main_data[LdJson.category]
        self.game.description = main_data[LdJson.description]
        self.game.image_link = main_data[LdJson.image]

    def set_price_data(self, cache_data):
        for cta_id in self.cta_ids:
            if cta_id and cta_id in cache_data:
                game = cache_data[cta_id]
                if AppJson.price in game:
                    price_data = game[AppJson.price]
                    if price_data[AppJson.upsell] == AppJson.upsell_evaluation:
                        continue
                    if not self.found_price:
                        self.game.base_price = price_data[AppJson.base_price]
                        self.game.found_price = True
                    if price_data[AppJson.service] == AppJson.empty_service:
                        self.game.discounted_price = price_data[AppJson.discount]
                        self.game.discount_percent = price_data[AppJson.discount_percent]
                    elif AppJson.plus_service in price_data[AppJson.service]:
                        self.game.plus_discount = price_data[AppJson.discount]
                        self.game.plus_percent = price_data[AppJson.discount_percent]


class PSBrowser:
    def __init__(self, game: GameInfo):
        self.game = game

    def retrieve_info(self):
        r = requests.get(self.game.link)
        return r.text
