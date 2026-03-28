"""Cliente asíncrono de Redis para caching con connection pool."""

import logging
from typing import Any, Optional

import redis.asyncio as redis
from redis.asyncio import ConnectionPool, Redis
from redis.exceptions import RedisError

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Cliente asíncrono de Redis con connection pool.
    
    Implementa el patrón Singleton para reutilizar la conexión
    y el pool de conexiones en toda la aplicación.
    """

    _instance: Optional["RedisClient"] = None
    _pool: Optional[ConnectionPool] = None
    _client: Optional[Redis] = None

    def __init__(self, redis_url: str, max_connections: int = 10):
        """
        Inicializar cliente de Redis.
        
        Args:
            redis_url: URL de conexión a Redis (ej: redis://localhost:6379/0)
            max_connections: Máximo número de conexiones en el pool
        """
        self.redis_url = redis_url
        self.max_connections = max_connections

    @classmethod
    async def get_instance(cls) -> "RedisClient":
        """
        Obtener instancia singleton del cliente Redis.
        
        Returns:
            RedisClient: Instancia única del cliente
        """
        if cls._instance is None:
            settings = get_settings()
            cls._instance = cls(
                redis_url=settings.redis_url,
                max_connections=10
            )
            await cls._instance.connect()
        return cls._instance

    async def connect(self) -> None:
        """
        Establecer conexión con Redis creando el connection pool.
        """
        if self._pool is None:
            self._pool = ConnectionPool.from_url(
                self.redis_url,
                max_connections=self.max_connections,
                decode_responses=True
            )
            self._client = Redis(connection_pool=self._pool)
            logger.info(f"✅ Redis conectado: {self.redis_url}")

    async def disconnect(self) -> None:
        """
        Cerrar conexión con Redis y liberar el connection pool.
        """
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        if self._pool is not None:
            await self._pool.disconnect()
            self._pool = None
        logger.info("✅ Redis desconectado")

    async def get(self, key: str) -> Optional[str]:
        """
        Obtener valor de Redis por clave.
        
        Args:
            key: Clave del valor a obtener
            
        Returns:
            El valor almacenado o None si no existe
        """
        if self._client is None:
            logger.warning("Redis no está conectado")
            return None
        
        try:
            value = await self._client.get(key)
            return value
        except RedisError as e:
            logger.error(f"Error obteniendo clave '{key}': {e}")
            return None

    async def set(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Establecer valor en Redis con TTL opcional.
        
        Args:
            key: Clave del valor a establecer
            value: Valor a almacenar
            ttl: Tiempo de vida en segundos (opcional)
            
        Returns:
            True si se estableció correctamente, False en caso de error
        """
        if self._client is None:
            logger.warning("Redis no está conectado")
            return False
        
        try:
            if ttl is not None:
                await self._client.setex(key, ttl, value)
            else:
                await self._client.set(key, value)
            return True
        except RedisError as e:
            logger.error(f"Error estableciendo clave '{key}': {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Eliminar clave de Redis.
        
        Args:
            key: Clave a eliminar
            
        Returns:
            True si se eliminó, False en caso de error
        """
        if self._client is None:
            logger.warning("Redis no está conectado")
            return False
        
        try:
            await self._client.delete(key)
            return True
        except RedisError as e:
            logger.error(f"Error eliminando clave '{key}': {e}")
            return False

    async def exists(self, key: str) -> bool:
        """
        Verificar si una clave existe en Redis.
        
        Args:
            key: Clave a verificar
            
        Returns:
            True si existe, False en caso contrario
        """
        if self._client is None:
            logger.warning("Redis no está conectado")
            return False
        
        try:
            exists = await self._client.exists(key)
            return bool(exists)
        except RedisError as e:
            logger.error(f"Error verificando clave '{key}': {e}")
            return False

    async def health_check(self) -> bool:
        """
        Verificar estado de la conexión con Redis.
        
        Returns:
            True si Redis está conectado y responde, False en caso contrario
        """
        if self._client is None:
            return False
        
        try:
            await self._client.ping()
            return True
        except RedisError as e:
            logger.error(f"Redis health check falló: {e}")
            return False

    @property
    def client(self) -> Optional[Redis]:
        """
        Obtener el cliente Redis subyacente.
        
        Returns:
            El cliente Redis o None si no está conectado
        """
        return self._client


# =============================================================================
# Dependency Provider para FastAPI
# =============================================================================


async def get_redis() -> RedisClient:
    """
    Dependency provider para obtener el cliente Redis en endpoints FastAPI.
    
    Usage en FastAPI:
        @app.get("/cache")
        async def get_cached(redis: RedisClient = Depends(get_redis)):
            value = await redis.get("key")
            return {"value": value}
    
    Returns:
        RedisClient: Instancia singleton del cliente Redis
    """
    return await RedisClient.get_instance()


# =============================================================================
# Shutdown handler para cerrar conexión graceful
# =============================================================================


async def shutdown_redis() -> None:
    """
    Cerrar conexión con Redis durante el shutdown de la aplicación.
    
    Usage en lifespan de FastAPI:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Startup
            yield
            # Shutdown
            await shutdown_redis()
    """
    if RedisClient._instance is not None:
        await RedisClient._instance.disconnect()
        RedisClient._instance = None
