import requests
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

class CardsAPIClient:
  BASE_URL = "https://restagainsthumanity.com/api/v2"

  DEFAULT_PACKS = ["CAH Base Set", "CAH: First Expansion", "CAH: Second Expansion", "CAH: Third Expansion"]

  def __init__(self):
    self.session = requests.Session()
    self.session.headers.update({
      'User-Agent': 'Django-Cards-Against-Humanity/1.0',
      'Accept': 'application/json'
    })

  def get_available_packs(self):
    """Fetch list of available card packs"""
    cache_key = "available_packs"
    packs = cache.get(cache_key)
    
    if not packs:
      try:
        response = self.session.get(f"{self.BASE_URL}/packs")
        response.raise_for_status()
        packs = response.json()
        # Cache for 24 hours
        cache.set(cache_key, packs, settings.CACHE_TTL.get('api_packs', 86400))
      except requests.RequestException as e:
        logger.error(f"Failed to fetch available packs: {e}")
        return self._get_fallback_packs()
    
    return packs

  def get_cards(self, packs=None):
    """Fetch cards from specified packs (defaults to Geek Pack)"""
    if packs is None:
      packs = ["Geek Pack"]  # DEFAULT TO GEEK PACK
    
    # Create cache key from pack names (sanitize for memcached compatibility)
    pack_string = '_'.join(sorted(packs)).replace(' ', '_').replace(':', '')
    cache_key = f"cards_{pack_string}"
    cards = cache.get(cache_key)
    
    if not cards:
      try:
        # v2 API expects comma-separated pack names
        packs_param = ",".join(packs)
        response = self.session.get(
          f"{self.BASE_URL}/cards", 
          params={'packs': packs_param}
        )
        response.raise_for_status()
        cards = response.json()
        
        # Cache for 1 hour
        cache.set(cache_key, cards, settings.CACHE_TTL.get('api_cards', 3600))
      except requests.RequestException as e:
        logger.error(f"Failed to fetch cards from packs {packs}: {e}")
        return self._get_fallback_cards()
    
    return cards

  def get_black_cards(self, count=1, packs=None):
    """Get random black cards (questions) with improved caching"""
    if packs is None:
      packs = ["Geek Pack"]  # DEFAULT TO GEEK PACK
    
    # Check if we have cached black cards (sanitize for memcached compatibility)
    pack_string = '_'.join(sorted(packs)).replace(' ', '_').replace(':', '')
    cache_key = f"black_cards_pool_{pack_string}"
    black_cards_pool = cache.get(cache_key)
    
    if not black_cards_pool:
      all_cards = self.get_cards(packs)
      black_cards_pool = all_cards.get('black', [])
      # Cache the pool for 30 minutes
      cache.set(cache_key, black_cards_pool, 1800)
    
    if len(black_cards_pool) < count:
      logger.warning(f"Only {len(black_cards_pool)} black cards available, requested {count}")
      return black_cards_pool
    
    import random
    return random.sample(black_cards_pool, count)

  def get_white_cards(self, count=10, packs=None):
    """Get random white cards (answers) with improved caching"""
    if packs is None:
      packs = ["Geek Pack"]  # DEFAULT TO GEEK PACK
    
    # Check if we have cached white cards (sanitize for memcached compatibility)
    pack_string = '_'.join(sorted(packs)).replace(' ', '_').replace(':', '')
    cache_key = f"white_cards_pool_{pack_string}"
    white_cards_pool = cache.get(cache_key)
    
    if not white_cards_pool:
      all_cards = self.get_cards(packs)
      white_cards_pool = all_cards.get('white', [])
      # Cache the pool for 30 minutes
      cache.set(cache_key, white_cards_pool, 1800)
    
    if len(white_cards_pool) < count:
      logger.warning(f"Only {len(white_cards_pool)} white cards available, requested {count}")
      return white_cards_pool
    
    import random
    return random.sample(white_cards_pool, count)

  def _get_fallback_packs(self):
    """Fallback pack list if API is down"""
    return [
      "Geek Pack",
      "Science Pack",
      "World Wide Web Pack",
      "CAH Base Set"
    ]

  def _get_fallback_cards(self):
    """Backup cards if API is down"""
    return {
      "black": [
        {
          "text": "Why can't I sleep at night?",
          "pick": 1,
          "pack": "Fallback Pack"
        },
        {
          "text": "What's that smell?",
          "pick": 1,
          "pack": "Fallback Pack"
        },
        {
          "text": "I got 99 problems but _____ ain't one.",
          "pick": 1,
          "pack": "Fallback Pack"
        },
        {
          "text": "_____ + _____ = _____",
          "pick": 3,
          "pack": "Fallback Pack"
        }
      ],
      "white": [
        {
          "text": "A disappointing birthday party",
          "pack": "Fallback Pack"
        },
        {
          "text": "Robots",
          "pack": "Fallback Pack"
        },
        {
          "text": "Poor life choices",
          "pack": "Fallback Pack"
        },
        {
          "text": "Existential dread",
          "pack": "Fallback Pack"
        },
        {
          "text": "The heart of a child",
          "pack": "Fallback Pack"
        },
        {
          "text": "Debugging CSS at 3 AM",
          "pack": "Developer Pack"
        },
        {
          "text": "Merge conflicts",
          "pack": "Developer Pack"
        },
        {
          "text": "Stack Overflow addiction",
          "pack": "Developer Pack"
        },
        {
          "text": "Deploying to production on Friday",
          "pack": "Developer Pack"
        },
        {
          "text": "Reading documentation",
          "pack": "Developer Pack"
        }
      ]
    }

# Global instance
cards_api = CardsAPIClient()
