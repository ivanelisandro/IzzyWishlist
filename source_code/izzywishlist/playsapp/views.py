from django.conf import settings
from django.shortcuts import redirect
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['games'] = self.wish.get_sorted_games()
        return context

    def post(self, request, *args, **kwargs):
        if request.method == 'POST':  # If method is POST,
            game_link = request.POST.get('game_link')
            game_delete = request.POST.get('game_delete')
            if game_link:
                self.wish.add_game(game_link)
            if game_delete:
                self.wish.remove_game(game_delete)

        return redirect('/ps')


class WishList:
    default_game_link = ''

    def __init__(self):
        self.links = []
        self.games = []
        self.load_links()
        self.reload_games()

    @staticmethod
    def is_valid_link(link: str):
        return link and link.startswith(WishList.default_game_link)

    def load_links(self):
        if len(self.links) > 0:
            return
        with open(settings.PLAYSAPP_LINKS_PATH, encoding='utf-8') as file:
            for line in file.read().splitlines():
                if line:
                    self.links.append(line)

    def save_links(self):
        with open(settings.PLAYSAPP_LINKS_PATH, mode='w', encoding='utf-8') as file:
            file.writelines('\n'.join(self.links))

    def add_game(self, link):
        if not self.is_valid_link(link):
            return

        self.links.append(link)
        thread = threading.Thread(target=self.load_game, args=(link,))
        thread.start()
        self.save_links()
        thread.join()

    def remove_game(self, link):
        _link_to_remove = ''
        _game_to_remove = None
        for game in self.games:
            if game.link == link:
                _game_to_remove = game
                _link_to_remove = link

        if _game_to_remove in self.games:
            self.games.remove(_game_to_remove)
        else:
            print("Cannot remove game. Game not found.")
        if _link_to_remove in self.links:
            self.links.remove(_link_to_remove)
        else:
            print("Cannot remove link. Link not found.")
        self.save_links()

    def reload_required(self):
        _game_added = False
        for link in self.links:
            for game in self.games:
                if game.link == link:
                    break
            else:
                return True

    def reload_games(self):
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

    def get_sorted_games(self):
        if self.reload_required():
            print("RELOADING")
            self.reload_games()
        sorted_games = sorted(self.games, key=operator.attrgetter('name'))
        return [game.to_dict() for game in sorted_games]


class GameInfo:
    included = 'Incluído'

    def __init__(self, link):
        self.link = link
        self.product_id = link.rstrip("/").split("/")[-1]
        self.name = ''
        self.category = ''
        self.platforms = []
        self.description = ''
        self.image_link = ''
        self.base_price = ''
        self.discounted_price = ''
        self.discount_percent = ''
        self.plus_discount = ''
        self.plus_percent = ''

    def format_discount(self, discount, percent, is_plus=False):
        _formatted = None
        if discount and discount != self.base_price:
            if discount == self.included:
                _formatted = f'R$ 0,00 ({percent})'
            else:
                _formatted = f'{discount} ({percent})'
        if _formatted and is_plus:
            _formatted = f'w/ Plus: {_formatted}'

        return _formatted

    def to_dict(self):
        return {
            'product_id': self.product_id,
            'link': self.link,
            'image_link': f"{self.image_link}?w=150",
            'name': self.name,
            'category': self.category,
            'platforms': self.platforms,
            'base_price': self.base_price,
            'discounted_price': self.format_discount(self.discounted_price, self.discount_percent),
            'plus_discount': self.format_discount(self.plus_discount, self.plus_percent, True),
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
    platforms = 'platforms'
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
                self.set_platforms(cache)
                self.set_price_data(cache)

    def set_main_data(self, data):
        main_data = json.loads(data)
        self.game.name = main_data[LdJson.name]
        self.game.category = main_data[LdJson.category]
        self.game.description = main_data[LdJson.description]
        self.game.image_link = main_data[LdJson.image]

    def set_platforms(self, cache_data):
        product_key = AppJson.product + self.game.product_id
        if product_key in cache_data:
            product = cache_data[product_key]
            if AppJson.platforms in product:
                self.game.platforms = product[AppJson.platforms]

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
