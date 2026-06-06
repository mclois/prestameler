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

## Módulos da app

### 1. `books` — Información de libros
Extrae e cachea información de libros dende APIs externas.

**Modelos**
- `Collection`: lista de libros (por xénero, colección, resultado de busca...)
  - `title`, `description`, `cover_image`
  - `book_count`, `selection_author`
  - Caché: `cid`, `cached_at`, `cache_ttl`, `tags`
- `Book`: libro con datos básicos
  - `title`, `author`, `cover_image`, `language`, `rating`
  - `external_id` (da API orixe)
  - FK → `Edition` (lista de edicións)
  - Caché: `cid`, `cached_at`, `cache_ttl`, `tags`
- `Edition`: edición concreta dun libro
  - `isbn` (identificador para busca de dispoñibilidade)
  - `format`: físico / ePub / PDF / audiolibro / ...
  - `publisher`, `published_date`
  - Caché: `cid`, `cached_at`, `cache_ttl`, `tags`

**Capas**
- `repositories/base.py`: interface `BookRepositoryBase` (ABC)
- `repositories/hardcover.py`: implementación para Hardcover API
- `repositories/openlibrary.py`: implementación para OpenLibrary (futuro)
- `repositories/google_books.py`: implementación para Google Books (futuro)
- `managers.py`: `BookManager` — carga local ou delega no repo activo

**APIs de terceiros**
- Principal: **Hardcover** (GraphQL API)
- Secundaria/fallback: **OpenLibrary** (REST, gratuíta e sen clave)
- Posible combinación: Hardcover para descubrimento, OpenLibrary para ISBNs

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
  - Caché: `cid`, `cached_at`, `cache_ttl`, `tags`
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
- [ ] Se combinar Hardcover + OpenLibrary ou só un
- [ ] Arquitectura concreta de `filter` (o Manager actual pode ser suficiente)
- [ ] Framework CSS para os templates (Bootstrap, Tailwind, ningún?)
- [ ] Deploy: servidor, containerización (Docker?)
