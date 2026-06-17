# Prestameler — Contexto do proxecto

## Que é
App Django para descubrir ebooks e consultar a súa dispoñibilidade de préstamo
nas bibliotecas da rede eBiblio España.

## Stack principal
- **Backend**: Django + httpx (síncrono por agora)
- **Frontend**: Django templates + HTML/CSS/JS clásico
- **BD**: PostgreSQL (ou SQLite en desenvolvemento)
- **Caché**: Django cache framework (backend a decidir: Redis / BD)
- **Validación/DTOs**: Pydantic v2
- **Tests**: pytest + pytest-django

## Idiomas

A app é multiidioma en dous sentidos independentes:

- **Idioma de interface**: Django i18n (`USE_I18N = True`). Por defecto español (`es`). Preparado para engadir outros idiomas sen cambios de arquitectura (gettext, ficheiros `.po`).
- **Idioma dos libros (filtro)**: parámetro libre de busca, sen restrición. Non se limita a ningún idioma; pásase directamente ás APIs de terceiros tal como veña do usuario.

A app `availability` non se ve afectada: os libros identifícanse por ISBN, que é neutro ao idioma.

## Principios de implementación
- Type hints en todo o código
- DTOs explícitos con Pydantic para transferencia de datos entre capas
- Tests dende o principio (unitarios para managers/repos, integración para vistas)
- Arquitectura en capas: Models → Repository → Manager → View/API
- Os repositorios illán completamente as APIs de terceiros do resto da app
- Os managers usan modelos locais como caché; só chaman ao repo se os datos
  non existen ou expiraron

---

## Mixin de caché — `CacheableModel`

Modelo abstracto do que herdan todos os modelos que actúan como caché de datos externos.

```python
class CacheableModel(models.Model):
    DEFAULT_CACHE_TTL: int = 3600       # override en cada subclase
    CID_FIELD: ClassVar[str]            # nome do campo ID externo; obrigatorio en cada subclase

    cached_at = models.DateTimeField(auto_now=True)
    cache_ttl = models.PositiveIntegerField()
    source    = models.CharField(max_length=50, db_index=True)

    class Meta:
        abstract = True

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not cls._meta.abstract and not hasattr(cls, 'CID_FIELD'):
            raise TypeError(f"{cls.__name__} debe declarar CID_FIELD")

    def save(self, *args, **kwargs):
        if not self.cache_ttl:
            self.cache_ttl = self.DEFAULT_CACHE_TTL
        super().save(*args, **kwargs)

    @property
    def cid(self) -> str:
        return getattr(self, self.CID_FIELD)

    @classmethod
    def get_cached(cls, cid: str) -> Self | None:
        return cls.objects.filter(**{cls.CID_FIELD: cid}).first()

    @property
    def is_stale(self) -> bool:
        expiry = self.cached_at + timedelta(seconds=self.cache_ttl)
        return timezone.now() > expiry
```

**Responsabilidades e decisións de deseño**

- `CID_FIELD`: constante de clase que indica cal é o campo ID externo nesa subclase (ex. `"isbn"` en `Edition`, `"hardcover_id"` en `Book`). Obrigatorio; `__init_subclass__` forza un erro en tempo de definición se se esquece.
- `cid` (property): devolve `getattr(self, self.CID_FIELD)`. Interface uniforme para as capas superiores sen coñecer o campo concreto.
- `get_cached(cid)`: classmethod para lookup na caché. O manager usa `Edition.get_cached(isbn, "hardcover")` sen necesidade de coñecer o nome do campo. O `**{cls.CID_FIELD: ...}` queda encapsulado no mixin.
- `cache_ttl`: persistido en BD (permite invalidar instancias concretas poñéndoo a `0`). O valor por defecto defínese como `DEFAULT_CACHE_TTL` en cada subclase; o repositorio non coñece nin establece este valor.
- `source`: valor fixo definido polo repositorio que crea a instancia (ex. `"hardcover"`, `"openlibrary"`). Permite invalidar por orixe: `Book.objects.filter(source="hardcover").update(cache_ttl=0)`. Non se usa para identificar rexistros, se o `cid` está na caché e non caducou se asume que os datos son correctos independentemente do source do que proveñan
- **PK**: Django xera `id` (AutoField enteiro) automaticamente. A identidade de dominio vai en `unique_together = [('<cid_field>', 'source')]` na `Meta` de cada subclase.

**Patrón de invalidación por orixe**
```python
# Invalidar toda a caché dun repositorio concreto
Book.objects.filter(source="openlibrary").update(cache_ttl=0)
Copy.objects.filter(source="eBiblio Galicia").update(cache_ttl=0)
# Na seguinte chamada ao manager, is_stale=True forzará refresco
```

**Patrón no repositorio**
```python
class HardcoverRepository(BookRepositoryBase):
    SOURCE = "hardcover"

    def fetch(self, ...) -> Book:
        return Book(source=self.SOURCE, hardcover_id=..., ...)
```

**Patrón no manager**
```python
book = Book.get_cached(hardcover_id, "hardcover")
if book is None or book.is_stale:
    book = self.repo.fetch(hardcover_id)
    book.save()
```

---

## Módulos da app

### 1. `books` — Información de libros
Extrae e cachea información de libros dende APIs externas.

**Modelos**
- `Collection`: lista de libros (por xénero, colección, resultado de busca...)
  - `title`, `description`, `cover_image`
  - `book_count`, `selection_author`
  - Caché: `cid` (ID da colección na API orixe), `cached_at`, `cache_ttl`, `source`
- `Book`: libro con datos básicos
  - `title`, `author`, `cover_image`, `language`, `rating`
  - FK → `Edition` (lista de edicións)
  - Caché: `cid` (ID do libro na API orixe, ex. Hardcover slug/ID), `cached_at`, `cache_ttl`, `source`
- `Edition`: edición concreta dun libro
  - `isbn` (identificador para busca de dispoñibilidade; coincide con `cid`)
  - `format`: físico / ePub / PDF / audiolibro / ...
  - `publisher`, `published_date`
  - Caché: `cid` (ISBN), `cached_at`, `cache_ttl`, `source`

**Capas**
- `repositories/base.py`: interface `BookRepositoryBase` (ABC)
- `repositories/hardcover.py`: implementación para Hardcover API (principal)
- `repositories/openlibrary.py`: implementación para OpenLibrary (fallback de ISBNs e metadatos)
- `managers.py`: `BookManager` — carga local ou delega no repo activo

**APIs de terceiros — decisión adoptada**

| API | Rol | Notas |
|-----|-----|-------|
| **Hardcover** | Principal — descubrimento e comunidade | GraphQL. Gratuíto (beta). Token con rexistro gratuíto. 60 req/min. Ofrece coleccions, series, valoracións, listas de usuarios, tags e contadores de lectores. Cobertura en español limitada pero crecendo. |
| **Open Library** | Fallback — metadatos e ISBNs | REST. Gratuíto e sen clave. +20M obras. Filtro por idioma (`language:spa`, `language:cat`…). Forte en clásicos; datos irregulares en edicións modernas. Non deseñada para tráfico alto. |
| **Google Books** | Descartada | Boa amplitude de catálogo pero termos prohíben monetización dos datos e carece de datos de comunidade na API pública. |

**APIs para o futuro (non implementar agora)**
- **LibraryThing** (`multirecommendations`): endpoint público que recibe un ou varios ISBNs e devolve recomendacións baseadas na comunidade — o "outros lectores tamén leron" que nin Hardcover nin Open Library ofrecen nativamente. Require API key gratuíta. Gardar para cando o módulo de descubrimento estea maduro.
- **StoryGraph**: 5M+ usuarios, excelente en recomendacións por humor/estado de ánimo, pero sen API oficial (só scraping fraxil con cookies). Descartar ata que publiquen API.

### 2. `availability` — Dispoñibilidade en bibliotecas
Comproba se un ebook se pode emprestar nalgunha biblioteca de eBiblio.

**Modelos**
- `Catalog`: catálogo da rede por comunidade autónoma
  - `name`, `community` (autonomous community), `base_url`
  - `backend`: tipo de implementación (`odilo` | `web`)
- `Copy`: exemplar emprestable
  - `isbn`, FK → `Catalog`
  - `available` (bool ou null se non informado)
  - `borrow_url`
  - Caché: `cid` (ID do exemplar na API Odilo / URL canónica), `cached_at`, `cache_ttl`, `source`
  - Nota: título, autor, portada... non se almacenan aquí; son responsabilidade de `Book`/`Edition`

**Capas**
- `repositories/base.py`: interface `AvailabilityRepositoryBase` (ABC)
  - método principal: `search(isbn: str) -> list[CopyDTO]`
- `repositories/odilo.py`: implementación para catálogos con backend Odilo (OAuth2 client_credentials + endpoint JSON `/opac/api/v2/records`)
- `repositories/ebiblio_web.py`: implementación para catálogos sen Odilo (scraping HTML)
- `managers.py`: `AvailabilityManager` — orquestra caché e repos; devolve `list[Copy]`
  - Itera os catálogos activos; por cada un comproba se a `Copy` en caché existe e non está obsoleta
  - Se a caché é válida, devolve o modelo directamente; se non, chama o repo correspondente e persiste o resultado
  - Non existe `CompositeRepository`: o manager contén o `_REGISTRY` e despacha directamente ao backend axeitado

**Patrón no manager**
```python
_REGISTRY = { Catalog.ODILO: OdiloRepository, Catalog.WEB: EbiblioWebRepository }

for catalog in Catalog.objects.filter(is_active=True):
    cached = Copy.objects.filter(isbn=isbn, catalog=catalog).first()
    if cached is not None and not cached.is_stale:
        results.append(cached)
    else:
        fresh = _REGISTRY[catalog.backend](catalog).search(isbn)
        for dto in fresh:
            dto.catalog_id = catalog.id
            dto.source = catalog.name
            results.append(Copy.update_cache(dto))
```

**Notas eBiblio**
- Non hai API pública documentada
- A plataforma usa **Odilo** como backend, baixo `/opac/api/v2/`. Confirmado con
  `https://biblioteca.ebiblio.cat` (Cataluña):
  - **Auth**: OAuth2 `client_credentials`. `POST {base_url}/opac/api/v2/token` con
    `Authorization: Basic <client_id:client_secret>` (par específico de cada catálogo,
    extraído do JS público do frontend OPAC; gardado en `Catalog.odilo_client_id` /
    `Catalog.odilo_client_secret`) e body `grant_type=client_credentials` →
    `{"access_token": ..., "expires_in": ...}`
  - **Busca**: `GET {base_url}/opac/api/v2/records?facets=format_facet_ss:"EBOOK"&query=allfields_txt:{isbn}&availability=true`
    con `Authorization: Bearer <token>` → array JSON de rexistros (`id`, `isbn`,
    `availability.availableToCheckout`, ...)
  - **Detalle**: `{base_url}/info/{id}` (o `id` Odilo do rexistro, non o ISBN)
- Catálogos coñecidos: galicia, extremadura (backend `web`), catalunya (backend `odilo`),
  madrid, andalucia, ... (lista a ampliar)

### 3. `filter` — Motor de busca e interfaces públicas

**Capas**
- `managers.py`: `FilterManager` — orquestra `BookManager` + `AvailabilityManager`
  - Obtén lista de libros/edicións
  - Cruza ISBNs coa dispoñibilidade
  - Devolve só edicións emprestables (ou todas, marcadas)
- `views.py`: vistas Django (Web UI)
- `api/v1`: Django REST Framework (headless, opcional/futuro)

**Páxinas Web UI**
- `/` — Portada con lista de coleccións
- `/search/` — Buscador por título, xénero, etc.
- `/collections/<id>/` — Libros dunha colección
- `/books/<id>/` — Detalle do libro + copias dispoñibles

---

## Estrutura de carpetas
```
prestameler/
├── config/                  # settings, urls, wsgi
├── books/
│   ├── models.py
│   ├── managers.py
│   ├── dtos.py              # Pydantic DTOs
│   ├── repositories/
│   │   ├── base.py
│   │   ├── hardcover.py
│   │   └── openlibrary.py
│   └── tests/
├── availability/
│   ├── models.py
│   ├── managers.py
│   ├── dtos.py
│   ├── repositories/
│   │   ├── base.py
│   │   └── ebiblio.py
│   └── tests/
├── filter/
│   ├── managers.py
│   ├── dtos.py
│   ├── views.py
│   ├── urls.py
│   ├── api/                 # DRF (futuro)
│   └── tests/
└── templates/
    ├── base.html
    ├── books/
    └── filter/
```

---

## Pendente de decidir
- [ ] Confirmar endpoint JSON real de eBiblio (inspeccionar DevTools)
- [ ] Credenciais/autenticación para Hardcover API
- [ ] Backend de caché (Redis vs BD)
- [ ] Arquitectura concreta de `filter` (o Manager actual pode ser suficiente)
- [ ] Framework CSS para os templates (Bootstrap, Tailwind, ningún?)
- [ ] Deploy: servidor, containerización (Docker?)

## Decisións adoptadas
- [x] **APIs de libros**: Hardcover (principal) + Open Library (fallback ISBNs). Google Books descartada.
- [x] **Recomendacións "tamén leron"**: LibraryThing `multirecommendations` gardado para fase futura.
- [x] **Mixin de caché**: `CacheableModel` abstracto con `cached_at`, `cache_ttl`, `source`. Sen campo `cid` — en súa lugar, `CID_FIELD` (constante de clase) apunta ao campo semántico propio de cada subclase (ex. `isbn`, `hardcover_id`). `cid` property devolve ese valor. `get_cached(cid)` encapsula o lookup. `__init_subclass__` forza que toda subclase concreta declare `CID_FIELD`. PK: `id` enteiro automático de Django; unicidade de dominio vía `unique_together`. Sen `tags` (YAGNI).
