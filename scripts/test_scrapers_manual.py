"""
Script manual para probar scrapers en vivo.

Uso:
    python -m scripts.test_scrapers_manual

Requiere:
    - .env configurado con ELTOQUE_API_KEY
    - Conexión a internet
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


async def test_all_scrapers():
    """Probar todos los scrapers en vivo."""
    from src.scrapers import fetch_eltoque, fetch_binance, fetch_cadeca, fetch_bcc
    
    print("=" * 60)
    print("TEST MANUAL DE SCRAPERS - TASALO API")
    print("=" * 60)
    
    # 1. ElToque
    print("\n1. Probando ElToque API...")
    eltoque_key = os.getenv("ELTOQUE_API_KEY", "")
    eltoque_url = os.getenv("ELTOQUE_API_URL", "https://tasas.eltoque.com/v1/trmi")
    
    if not eltoque_key:
        print("   ⚠️  ELTOQUE_API_KEY no configurada en .env")
    else:
        result = await fetch_eltoque(eltoque_key, eltoque_url)
        if result:
            print(f"   ✅ Éxito - Fecha: {result.get('fecha', 'N/A')}")
            tasas = result.get('tasas', {})
            if 'USD' in tasas:
                print(f"   💵 USD: {tasas['USD']:.2f} CUP")
            if 'EUR' in tasas:
                print(f"   💶 EUR: {tasas['EUR']:.2f} CUP")
        else:
            print("   ❌ Error - No se obtuvieron datos")
    
    # 2. Binance
    print("\n2. Probando Binance API...")
    result = await fetch_binance()
    if result:
        print(f"   ✅ Éxito - {len(result)} pares obtenidos")
        if 'BTCUSDT' in result:
            print(f"   ₿ BTC: ${result['BTCUSDT']:,.2f}")
        if 'ETHUSDT' in result:
            print(f"   Ξ ETH: ${result['ETHUSDT']:,.2f}")
    else:
        print("   ❌ Error - No se obtuvieron datos")
    
    # 3. CADECA
    print("\n3. Probando CADECA scraper...")
    result = await fetch_cadeca()
    if result:
        print(f"   ✅ Éxito - {len(result)} monedas obtenidas")
        if 'USD' in result:
            print(f"   💵 USD: Compra {result['USD']['compra']:.2f} / Venta {result['USD']['venta']:.2f}")
    else:
        print("   ❌ Error - No se obtuvieron datos (sitio puede estar caído)")
    
    # 4. BCC
    print("\n4. Probando BCC scraper...")
    result = await fetch_bcc()
    if result:
        print(f"   ✅ Éxito - {len(result)} monedas obtenidas")
        if 'USD' in result:
            print(f"   💵 USD Oficial: {result['USD']:.2f} CUP")
    else:
        print("   ❌ Error - No se obtuvieron datos (sitio puede estar caído)")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETADO")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_all_scrapers())
