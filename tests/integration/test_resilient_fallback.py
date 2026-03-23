"""Test simple de la estrategia resiliente - usa DB SQLite de prueba."""

import asyncio
import os
from datetime import datetime, timedelta, timezone

# Configurar DB de prueba ANTES de importar nada más
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_resilient.db"

from sqlalchemy import select, func, delete
from src.database import get_engine, async_session_factory, Base
from src.models.rate_snapshot import RateSnapshot
from src.services import rates_service


async def test_fallback_strategy():
    """
    Prueba la estrategia de fallback:
    1. Crea datos históricos falsos (hace 3 horas)
    2. Verifica que get_latest_rates usa fallback correctamente
    """
    print("\n" + "="*60)
    print("🧪 TEST: Estrategia Resiliente de Fallback")
    print("="*60 + "\n")
    
    # 1. Inicializar DB
    print("🔧 Inicializando base de datos de prueba...")
    engine = get_engine(os.environ["DATABASE_URL"], echo=False)
    
    # Crear tablas
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Asegurar que async_session_factory esté inicializada
    if async_session_factory is None:
        from src.database import async_session_factory as factory
        print(f"⚠️ async_session_factory es None, usando factory local: {factory}")
    
    print("✅ DB inicializada\n")
    
    # Usar la factory directamente del módulo
    from src.database import async_session_factory as session_factory
    
    async with session_factory() as session:
        # 2. Limpiar datos existentes
        print("🗑️ Limpiando datos existentes...")
        await session.execute(delete(RateSnapshot))
        await session.commit()
        
        # 3. Crear datos históricos falsos (hace 3 horas)
        now = datetime.now(timezone.utc)
        old_timestamp = now - timedelta(hours=3)
        
        print(f"📝 Creando datos históricos falsos ({old_timestamp})...")
        
        test_data = [
            # ElToque - datos viejos
            RateSnapshot(source='eltoque', currency='USD', buy_rate=None, sell_rate=385.50, fetched_at=old_timestamp),
            RateSnapshot(source='eltoque', currency='EUR', buy_rate=None, sell_rate=415.20, fetched_at=old_timestamp),
            RateSnapshot(source='eltoque', currency='MLC', buy_rate=None, sell_rate=390.00, fetched_at=old_timestamp),
            
            # CADECA - datos viejos
            RateSnapshot(source='cadeca', currency='USD', buy_rate=122.00, sell_rate=128.00, fetched_at=old_timestamp),
            RateSnapshot(source='cadeca', currency='EUR', buy_rate=132.50, sell_rate=138.50, fetched_at=old_timestamp),
            
            # BCC - datos viejos
            RateSnapshot(source='bcc', currency='USD', buy_rate=None, sell_rate=122.00, fetched_at=old_timestamp),
            RateSnapshot(source='bcc', currency='EUR', buy_rate=None, sell_rate=132.50, fetched_at=old_timestamp),
            
            # Binance - datos viejos
            RateSnapshot(source='binance', currency='BTC', buy_rate=None, sell_rate=98500.00, fetched_at=old_timestamp),
            RateSnapshot(source='binance', currency='ETH', buy_rate=None, sell_rate=3250.00, fetched_at=old_timestamp),
        ]
        
        session.add_all(test_data)
        await session.commit()
        print(f"✅ {len(test_data)} registros históricos creados\n")
        
        # 4. Probar get_latest_rates con max_age_minutes=120 (datos de 3h deberían ser stale)
        print("🔄 Probando get_latest_rates(max_age_minutes=120)...")
        print("-" * 60 + "\n")
        
        rates = await rates_service.get_latest_rates(session, max_age_minutes=120)
        
        print("\n" + "-" * 60)
        print("📊 RESULTADOS:")
        print("-" * 60 + "\n")
        
        # 5. Verificar resultados
        total_rates = sum(len(rates[source]) for source in rates)
        print(f"Total de tasas obtenidas: {total_rates}")
        
        for source in ['eltoque', 'cadeca', 'bcc', 'binance']:
            source_rates = rates.get(source, {})
            print(f"\n{source.upper()}:")
            
            if not source_rates:
                print(f"  ❌ Sin datos")
            else:
                print(f"  ✅ {len(source_rates)} monedas:")
                for currency, data in source_rates.items():
                    if source == 'cadeca':
                        buy = data.get('buy', 'N/A')
                        sell = data.get('sell', 'N/A')
                        print(f"    {currency}: Buy={buy}, Sell={sell}")
                    else:
                        rate = data.get('rate', 'N/A')
                        age = data.get('data_age_minutes', 'N/A')
                        print(f"    {currency}: {rate} (edad: {age}min)")
        
        # 6. Verificaciones
        print("\n" + "="*60)
        print("✅ VERIFICACIONES:")
        print("="*60 + "\n")
        
        checks_passed = 0
        total_checks = 0
        
        # Check 1: ElToque tiene datos
        total_checks += 1
        if rates.get('eltoque'):
            print("✅ Check 1: ElToque tiene datos (fallback funcionó)")
            checks_passed += 1
        else:
            print("❌ Check 1: ElToque SIN datos (fallback falló)")
        
        # Check 2: CADECA tiene datos
        total_checks += 1
        if rates.get('cadeca'):
            print("✅ Check 2: CADECA tiene datos (fallback funcionó)")
            checks_passed += 1
        else:
            print("❌ Check 2: CADECA SIN datos (fallback falló)")
        
        # Check 3: BCC tiene datos
        total_checks += 1
        if rates.get('bcc'):
            print("✅ Check 3: BCC tiene datos (fallback funcionó)")
            checks_passed += 1
        else:
            print("❌ Check 3: BCC SIN datos (fallback falló)")
        
        # Check 4: Binance tiene datos
        total_checks += 1
        if rates.get('binance'):
            print("✅ Check 4: Binance tiene datos (fallback funcionó)")
            checks_passed += 1
        else:
            print("❌ Check 4: Binance SIN datos (fallback falló)")
        
        # Check 5: data_age_minutes está presente
        total_checks += 1
        has_age = False
        for source in rates:
            for currency in rates[source]:
                if 'data_age_minutes' in rates[source][currency]:
                    has_age = True
                    break
        if has_age:
            print("✅ Check 5: data_age_minutes está presente en respuestas")
            checks_passed += 1
        else:
            print("❌ Check 5: data_age_minutes FALTA en respuestas")
        
        # Resultado final
        print("\n" + "="*60)
        print(f"📈 RESULTADO FINAL: {checks_passed}/{total_checks} checks passed")
        print("="*60 + "\n")
        
        if checks_passed == total_checks:
            print("🎉 ¡TEST EXITOSO! La estrategia resiliente funciona correctamente.")
        else:
            print("⚠️ Algunos checks fallaron. Revisar logs arriba.")
        
        # 7. Limpiar DB de test
        print("\n🗑️ Limpiando base de datos de prueba...")
        await session.execute(delete(RateSnapshot))
        await session.commit()
        print("✅ DB limpiada")
        
        return checks_passed == total_checks


if __name__ == "__main__":
    success = asyncio.run(test_fallback_strategy())
    
    # Limpiar archivo DB
    if os.path.exists("test_resilient.db"):
        os.remove("test_resilient.db")
        print("🗑️ test_resilient.db eliminado")
    
    exit(0 if success else 1)
