from django.db import models

# No DB-backed model for chunks/embeddings anymore -- those now live in a
# local cache file (see embed_cache.py), loaded into memory by the API
# views. This file is kept around for whatever Django-native data comes
# later (e.g. saved conversations, user accounts).
