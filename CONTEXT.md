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
    DEFAULT_CACHE_TTL: int = 3600  # override en cada subclase

    cid       = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    cached_at = models.DateTimeField(auto_now=True)
    cache_ttl = models.PositiveIntegerField()          # valor por defecto posto no save()
    source    = models.CharField(max_length=50, db_index=True)  # obrigatorio, posto polo repo
    tags      = models.JSONField(default=list, blank=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.cache_ttl:
            self.cache_ttl = self.DEFAULT_CACHE_TTL
        super().save(*args, **kwargs)

    @property
    def is_stale(self) -> bool:
        expiry = self.cached_at + timedelta(seconds=self.cache_ttl)
        return timezone.now() > expiry
```

**Responsabilidades e decisións de deseño**

- `cache_ttl`: persistido en BD (permite invalidar instancias concretas poñéndoo a `0`). O valor por defecto defínese como constante de clase (`DEFAULT_CACHE_TTL`) en cada subclase; o repositorio non coñece nin establece este valor.
- `source`: valor fixo definido polo repositorio que crea a instancia (ex. `"hardcover"`, `"openlibrary"`). Permite invalidar por orixe: `Book.objects.filter(source="hardcover").update(cache_ttl=0)`.
- `tags`: campo libre para metadatos opcionais. Non se usa para source nin para invalidación estruturada.
- `cid`: identificador estable para referenciar o rexistro dende capas superiores sen expor a PK interna.

**Patrón de invalidación por orixe**
```python
# Invalidar toda a caché dun repositorio concreto
Book.objects.filter(source="openlibrary").update(cache_ttl=0)
Copy.objects.filter(source="odilo").update(cache_ttl=0)
# Na seguinte chamada ao manager, is_stale=True forzará refresco
```

**Patrón no repositorio**
```python
class HardcoverRepository(BookRepositoryBase):
    SOURCE = "hardcover"

    def fetch(self, ...) -> Book:
        return Book(source=self.SOURCE, ...)
```

---

## Módulos da app

### 1. `books` — Información de libros
Extrae e cachea información de libros dende APIs externas.

**Modelos**
- `Collection`: lista de libros (por xénero, colección, resultado de busca...)
  - `title`, `description`, `cover_image`
  - `book_count`, `selection_author`
  - Caché: `cid`, `cached_at`, `cache_ttl`, `source`, `tags`
- `Book`: libro con datos básicos
  - `title`, `author`, `cover_image`, `language`, `rating`
  - `external_id` (da API orixe)
  - FK → `Edition` (lista de edicións)
  - Caché: `cid`, `cached_at`, `cache_ttl`, `source`, `tags`
- `Edition`: edición concreta dun libro
  - `isbn` (identificador para busca de dispoñibilidade)
  - `format`: físico / ePub / PDF / audiolibro / ...
  - `publisher`, `published_date`
  - Caché: `cid`, `cached_at`, `cache_ttl`, `source`, `tags`

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
  - Caché: `cid`, `cached_at`, `cache_ttl`, `source`, `tags`
  - Nota: título, autor, portada... non se almacenan aquí; son responsabilidade de `Book`/`Edition`

**Capas**
- `repositories/base.py`: interface `AvailabilityRepositoryBase` (ABC)
  - método principal: `search(isbn: str) -> list[CopyDTO]`
- `repositories/odilo.py`: implementación para catálogos con backend Odilo (endpoint JSON)
- `repositories/ebiblio_web.py`: implementación para catálogos sen Odilo (scraping HTML)
- `repositories/composite.py`: `CompositeRepository(AvailabilityRepositoryBase)`
  - percorre os catálogos activos, instancia o repo correspondente segundo `catalog.backend`,
    mergea e devolve todos os resultados
  - o manager só fala con este repositorio, sen saber que existen N backends
- `managers.py`: `AvailabilityManager` — carga local ou delega en `CompositeRepository`

**Patrón de selección de backend en CompositeRepository**
```
REGISTRY = { ODILO: OdiloRepository, WEB: EbiblioWebRepository }
for catalog in Catalog.objects.filter(is_active=True):
    repo = REGISTRY[catalog.backend](catalog)
    copies += repo.search(isbn)
```

**Notas eBiblio**
- Non hai API pública documentada
- A plataforma usa **Odilo** como backend; as peticións son chamadas AJAX a un
  endpoint JSON (patrón: `https://{comunidade}.ebiblio.es/api/v1/resources?isbn=...`)
- Endpoint a confirmar inspeccionando tráfico de rede (DevTools → Fetch/XHR)
- Catálogos coñecidos: galicia, extremadura, madrid, andalucia, ... (lista a ampliar)

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
- [x] **Mixin de caché**: `CacheableModel` abstracto con `cid`, `cached_at`, `cache_ttl`, `source`, `tags`. `cache_ttl` persistido en BD e invalidable poñéndoo a `0`. `source` fixo por repositorio. `DEFAULT_CACHE_TTL` como constante de clase en cada subclase.
