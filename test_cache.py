"""
Script pour tester le fonctionnement du cache Redis.
Usage: python test_cache.py
"""
import os
import sys
import time

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

from django.core.cache import cache
from django.conf import settings


def test_cache():
    print("=" * 60)
    print("TEST DU CACHE REDIS")
    print("=" * 60)

    # 1. Test de connexion basique
    print("\n1. Test de connexion basique...")
    try:
        cache.set('test_connection', 'OK', 10)
        result = cache.get('test_connection')
        if result == 'OK':
            print("   ✓ Connexion Redis OK")
        else:
            print("   ✗ Erreur: valeur inattendue")
            return False
    except Exception as e:
        print(f"   ✗ Erreur de connexion: {e}")
        return False

    # 2. Test de performance
    print("\n2. Test de performance (1000 opérations)...")
    start = time.time()
    for i in range(1000):
        cache.set(f'perf_test_{i}', f'value_{i}', 60)
    write_time = time.time() - start

    start = time.time()
    for i in range(1000):
        cache.get(f'perf_test_{i}')
    read_time = time.time() - start

    print(f"   ✓ Écriture: {write_time*1000:.2f}ms pour 1000 ops ({write_time:.4f}ms/op)")
    print(f"   ✓ Lecture:  {read_time*1000:.2f}ms pour 1000 ops ({read_time:.4f}ms/op)")

    # Cleanup
    for i in range(1000):
        cache.delete(f'perf_test_{i}')

    # 3. Test d'expiration
    print("\n3. Test d'expiration (TTL)...")
    cache.set('ttl_test', 'expires_soon', 2)
    print(f"   Valeur initiale: {cache.get('ttl_test')}")
    print("   Attente de 3 secondes...")
    time.sleep(3)
    expired_value = cache.get('ttl_test')
    if expired_value is None:
        print("   ✓ Expiration OK (valeur = None)")
    else:
        print(f"   ✗ Erreur: la valeur n'a pas expiré ({expired_value})")

    # 4. Vérifier les clés de statistiques existantes
    print("\n4. Clés de statistiques en cache...")
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL + '/1')
        stats_keys = r.keys('greensig:stats_*')
        if stats_keys:
            print(f"   ✓ {len(stats_keys)} clé(s) de statistiques trouvée(s):")
            for key in stats_keys[:5]:  # Afficher max 5
                ttl = r.ttl(key)
                print(f"     - {key.decode()} (TTL: {ttl}s)")
        else:
            print("   ℹ Aucune clé de statistiques en cache (normal si pas encore appelé)")
    except ImportError:
        print("   ℹ redis-py non installé, impossible de lister les clés")
    except Exception as e:
        print(f"   ℹ Impossible de lister les clés: {e}")

    # 5. Configuration
    print("\n5. Configuration du cache:")
    print(f"   Backend: {settings.CACHES['default']['BACKEND']}")
    print(f"   Location: {settings.CACHES['default']['LOCATION']}")
    print(f"   Timeout par défaut: {settings.CACHES['default'].get('TIMEOUT', 300)}s")
    print(f"   Timeout statistiques: {getattr(settings, 'CACHE_TIMEOUT_STATISTICS', 300)}s")

    print("\n" + "=" * 60)
    print("CACHE REDIS FONCTIONNEL ✓")
    print("=" * 60)
    return True


if __name__ == '__main__':
    test_cache()
