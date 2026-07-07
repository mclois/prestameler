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

**Tradución de contido dinámico (Hardcover)**: o i18n de Django (gettext) só cobre texto estático (chrome da UI: labels, botóns, erros). Non serve para xéneros/moods/nomes de colección que veñen da API de Hardcover, xa que gettext precisa que as strings existan no código fonte en tempo de extracción. Estratexia:
- **Xéneros/moods**: vocabulario pechado e pequeno → tradúcense á man, unha vez, nunha táboa de tradución mantida coma datos estáticos.
- **Nomes de Collection/listas**: texto libre non acoutado (case nomes propios) → quedan sen traducir, amósanse tal cal veñan da API, independentemente do idioma de interface. Descartouse un pipeline de tradución automática (MT) + caché por ser sobrecuste innecesario para este caso.
- **Patrón elixido**: modelo `*Translation` separado por modelo traducible (`CollectionTranslation`, `FacetTranslation` — unha fila por `(obxecto, idioma)`), en troques de `django-modeltranslation` (columnas `name_es`/`name_gl`/... anchas na propia táboa). Motivo: cada fila de tradución garda un `source_name_snapshot` (valor do campo orixe no momento de traducir), o que permite que `is_stale` sexa unha property calculada (`snapshot != valor_actual_do_campo_orixe`) en vez dunha flag que haxa que lembrar actualizar en cada camiño de sync. Se a fonte cambia, a tradución existente non se borra — márcase coma obsoleta para que un editor a revise en vez de traducir de cero. `django-parler` xera esta mesma estrutura (táboa separada) automaticamente e é unha alternativa válida a avaliar se medra o número de modelos traducibles.
- Non implementar ata que `BookManager` e `FilterManager` estean rematados; forma parte das features de CMS/admin (inline en Django admin sobre o modelo de tradución).

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

- `CID_FIELD`: constante de clase que indica cal é o campo ID externo nesa subclase (ex. `"isbn"` en `Edition`, `"external_id"` en `Book` e `Collection`). Obrigatorio; `__init_subclass__` forza un erro en tempo de definición se se esquece.
- `cid` (property): devolve `getattr(self, self.CID_FIELD)`. Interface uniforme para as capas superiores sen coñecer o campo concreto.
- `get_cached(cid)`: classmethod para lookup na caché. O manager usa `Edition.get_cached(isbn)` sen necesidade de coñecer o nome do campo. O `**{cls.CID_FIELD: ...}` queda encapsulado no mixin.
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
        return Book(source=self.SOURCE, external_id=..., ...)
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
  - `title`, `author`, `language`, `format`, `cover_image`: metadatos do exemplar tal e como aparecen na fonte (Odilo/scraping web), non normalizados contra `Book`/`Edition` — permiten detectar adaptacións, traducións e outras versións "raras" mal agrupadas por Hardcover (#30)
  - Caché: `cid` (ID do exemplar na API Odilo / URL canónica), `cached_at`, `cache_ttl`, `source`

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

## Frontend / Templates

Frontend minimalista e responsive sobre Django templates renderizados no servidor.
Principio reitor: complementar o server-rendering, non loitar contra el (nada de SPA).

**Stack elixido**
- **CSS — Pico.css (classless, punto de partida)**: escríbese HTML semántico
  (`<nav>`, `<article>`, `<button>`) e obtense responsive + modo escuro case gratis,
  sen ensuciar os templates con clases. Se ao medrar as páxinas de detalle
  (`/books/<id>/`) se precisa control fino de layout, migrar a **Tailwind** é un
  cambio só de clases nos templates, sen tocar a lóxica. Deixar como porta aberta.
- **Interactividade — HTMX**: actualizacións parciais dende vistas que devolven
  *fragmentos* de template (buscador, filtros, paxinación), sen API JSON nin SPA.
  Encaixa co modelo de `filter/views.py`. Helper: paquete `django-htmx`
  (`request.htmx` no middleware).
- **Efectos JS locais — Alpine.js** (~15 KB, sen build step): pestañas, dropdowns,
  toggles, acordeóns. Os atributos (`x-show`, `@click`) son *comportamento*, non
  estilo → o CSS queda limpo e nun ficheiro aparte.
  *(Ollo ao implementar: fragmentos inseridos por HTMX poden necesitar
  `Alpine.initTree()` en `htmx:afterSwap` para que `x-data` se reinicialice.)*
- **Formularios**: `django-widget-tweaks` (lixeiro, engadir clases aos widgets no
  template) ou `django-crispy-forms` + pack correspondente. Decisión final ao
  implementar os forms reais.

**Descartados**
- **Bootstrap**: o seu valor histórico (grid de 12 columnas + normalización de
  navegadores) desapareceu con `flex`/`grid` nativos. Aporta compoñentes prefeitos
  pero cun aspecto xenérico recoñecible e un bundle CSS+JS de máis para este MVP.
- **Tailwind**: descartado por preferencia (proba previa negativa: sopa de clases no
  marcado, difícil de ler). Mantido só como plan B de migración se Pico queda curto.

**Carruseis da portada** (Featured, moods, xéneros)
- Non son sliders tipo *hero* (un slide grande con autoplay) senón **estantes**
  horizontais de tarxetas estilo streaming.
- Patrón elixido: **CSS `scroll-snap` nativo** — táctil (swipe/trackpad), sen JS,
  cero librarías:
  ```css
  .shelf {
    display: flex; gap: 1rem;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
    scroll-behavior: smooth;
  }
  .shelf > * { flex: 0 0 auto; scroll-snap-align: start; }
  ```
  ```html
  <section class="shelf">
    {% for col in featured %}{% include "books/_collection_card.html" %}{% endfor %}
  </section>
  ```
- Frechas ‹ › opcionais: ~10 liñas de JS vanilla (`el.scrollBy({left: 320, behavior: 'smooth'})`)
  ou o mesmo con Alpine.
- **Só se** algún día se precisa un slider pesado real (autoplay, puntos, loop
  infinito, *hero*): headless minúsculo tipo **Embla Carousel** (~6 KB) ou Splide.
  Para estantes de libros, `scroll-snap` gaña en peso e simplicidade.

**Reutilización de templates**
- Partials repetidos (tarxeta de libro, tarxeta de colección) vía `{% include %}`.
- Se se quere unha DX máis de compoñentes: `django-template-partials` ou
  `django-cotton`. Opcional, deixar para máis adiante.

**Pendente ao implementar**
- [ ] Decidir `widget-tweaks` vs `crispy-forms` cando existan os forms reais
- [ ] Definir o partial `_collection_card.html` e `_book_card.html`
- [ ] Confirmar se abonda con `scroll-snap` ou fai falla Embla nalgún estante

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
- [ ] Deploy: servidor, containerización (Docker?)
- [ ] Split de `filter` en apps separadas (`browser` para HTML público, `api` para DRF futuro,
      `filter` queda só coma orquestración). Xurdiu ao pensar nas páxinas públicas; sen decidir,
      retomar antes de empezar `browser`.

## Decisións adoptadas
- [x] **APIs de libros**: Hardcover (principal) + Open Library (fallback ISBNs). Google Books descartada.
- [x] **Recomendacións "tamén leron"**: LibraryThing `multirecommendations` gardado para fase futura.
- [x] **Mixin de caché**: `CacheableModel` abstracto con `cached_at`, `cache_ttl`, `source`. Sen campo `cid` — en súa lugar, `CID_FIELD` (constante de clase) apunta ao campo semántico propio de cada subclase (ex. `isbn` en `Edition`, `external_id` en `Book` e `Collection`). `cid` property devolve ese valor. `get_cached(cid)` encapsula o lookup. `__init_subclass__` forza que toda subclase concreta declare `CID_FIELD`. PK: `id` enteiro automático de Django; unicidade de dominio vía `unique_together`. Sen `tags` (YAGNI).
- [x] **Enriquecemento editorial**: módulo `editorial` (app Django independente) para datos curados manualmente que completan o que veñen dos repositorios externos (ex. portada dunha colección de Hardcover que non ten imaxe). Os modelos de `editorial` son permanentes (non herdan de `CacheableModel`, non expiran). O merge farase en `FilterManager` ao compoñer a resposta ao usuario. Non implementar ata que `books` e `filter` estean operativos.
- [x] **Tradución de contido dinámico**: ver detalle en [Idiomas](#idiomas). Táboas `*Translation` separadas (non `django-modeltranslation`) con snapshot da fonte para invalidación calculada. Non implementar ata que `BookManager`/`FilterManager` estean rematados.
- [x] **Stack frontend**: ver detalle en [Frontend / Templates](#frontend--templates). Pico.css (classless) + HTMX + Alpine.js. Bootstrap e Tailwind descartados.
