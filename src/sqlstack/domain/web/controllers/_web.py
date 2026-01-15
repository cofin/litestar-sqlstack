from __future__ import annotations

from litestar import Controller, MediaType, Response, get
from litestar.status_codes import HTTP_200_OK


class WebController(Controller):
    """Web Controller."""

    opt = {"exclude_from_auth": True}
    include_in_schema = False

    @get("/", operation_id="WebIndex", status_code=HTTP_200_OK, media_type=MediaType.HTML)
    async def index(self) -> Response[str]:
        """Serve landing page.

        Returns:
            Response: An HTTP Response with the landing page HTML
        """
        html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SQLStack - Litestar Reference Architecture</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }

        header {
            text-align: center;
            padding: 3rem 0;
            color: white;
        }

        h1 {
            font-size: 3rem;
            margin-bottom: 1rem;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }

        .tagline {
            font-size: 1.25rem;
            opacity: 0.95;
            margin-bottom: 2rem;
        }

        .content {
            background: white;
            border-radius: 12px;
            padding: 3rem;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            margin-bottom: 2rem;
        }

        .tech-stack {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 2rem;
            margin: 2rem 0;
        }

        .tech-card {
            padding: 1.5rem;
            background: #f8f9fa;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }

        .tech-card h3 {
            color: #667eea;
            margin-bottom: 0.5rem;
        }

        .tech-card p {
            color: #666;
            font-size: 0.95rem;
        }

        .section {
            margin: 3rem 0;
        }

        .section h2 {
            color: #333;
            margin-bottom: 1.5rem;
            font-size: 2rem;
            border-bottom: 2px solid #667eea;
            padding-bottom: 0.5rem;
        }

        .feature-list {
            list-style: none;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1rem;
        }

        .feature-list li {
            padding: 0.75rem;
            background: #f8f9fa;
            border-radius: 6px;
            display: flex;
            align-items: center;
        }

        .feature-list li:before {
            content: "✓";
            color: #667eea;
            font-weight: bold;
            margin-right: 0.75rem;
            font-size: 1.2rem;
        }

        .code-block {
            background: #2d2d2d;
            color: #f8f8f2;
            padding: 1.5rem;
            border-radius: 6px;
            overflow-x: auto;
            margin: 1rem 0;
        }

        .code-block pre {
            margin: 0;
            font-family: 'Courier New', Courier, monospace;
            font-size: 0.9rem;
        }

        .api-endpoints {
            background: #f8f9fa;
            padding: 1.5rem;
            border-radius: 8px;
            margin: 1rem 0;
        }

        .endpoint {
            display: flex;
            align-items: center;
            margin: 0.5rem 0;
            font-family: monospace;
        }

        .method {
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-weight: bold;
            margin-right: 1rem;
            font-size: 0.85rem;
            min-width: 60px;
            text-align: center;
        }

        .method.get { background: #61affe; color: white; }
        .method.post { background: #49cc90; color: white; }
        .method.put { background: #fca130; color: white; }
        .method.delete { background: #f93e3e; color: white; }

        footer {
            text-align: center;
            color: white;
            padding: 2rem 0;
            opacity: 0.9;
        }

        a {
            color: #667eea;
            text-decoration: none;
        }

        a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🚀 SQLStack</h1>
            <p class="tagline">Litestar Reference Architecture with SQLSpec</p>
            <p>A modern, production-ready application template showcasing best practices</p>
        </header>

        <div class="content">
            <section class="section">
                <h2>Technology Stack</h2>
                <div class="tech-stack">
                    <div class="tech-card">
                        <h3>🌟 Litestar</h3>
                        <p>Production-ready, lightweight ASGI framework for building performant APIs with full type checking support</p>
                    </div>
                    <div class="tech-card">
                        <h3>🗄️ SQLSpec</h3>
                        <p>Modern SQL toolkit with SQLGlot support, enabling type-safe database operations with named SQL queries</p>
                    </div>
                    <div class="tech-card">
                        <h3>🐘 PostgreSQL</h3>
                        <p>Powerful, open-source relational database with asyncpg for high-performance async operations</p>
                    </div>
                    <div class="tech-card">
                        <h3>📝 Pydantic & msgspec</h3>
                        <p>Data validation and serialization with automatic OpenAPI schema generation</p>
                    </div>
                </div>
            </section>

            <section class="section">
                <h2>Common Usage Patterns</h2>
                <ul class="feature-list">
                    <li>Named SQL queries stored in .sql files for maintainability</li>
                    <li>Service layer pattern with SQLSpecAsyncService base class</li>
                    <li>Automatic pagination with OffsetPagination</li>
                    <li>Type-safe query parameters using kwargs</li>
                    <li>Session-based authentication with role-based access control</li>
                    <li>Dependency injection for clean architecture</li>
                    <li>Structured logging with correlation IDs</li>
                    <li>Health checks and system monitoring endpoints</li>
                </ul>
            </section>

            <section class="section">
                <h2>Project Structure</h2>
                <div class="code-block">
                    <pre>sqlstack/
├── cli/              # CLI commands and utilities
├── config.py         # Central configuration (SQLSpec, CORS, logging)
├── db/
│   ├── migrations/   # Database schema migrations
│   ├── fixtures/     # Test and seed data
│   └── sql/          # Named SQL query files (core architecture)
├── lib/              # Core utilities (crypto, logging, settings)
├── schemas/          # Pydantic/msgspec schemas (DTOs)
├── server/
│   ├── routes/       # API endpoint controllers
│   ├── deps.py       # Dependency injection providers
│   ├── core.py       # Application core plugin
│   └── plugins.py    # Plugin configurations
├── services/         # Business logic layer
└── utils/            # Shared utilities</pre>
                </div>
            </section>

            <section class="section">
                <h2>Available API Endpoints</h2>
                <div class="api-endpoints">
                    <div class="endpoint">
                        <span class="method get">GET</span>
                        <span>/api/health</span> - Health check endpoint
                    </div>
                    <div class="endpoint">
                        <span class="method get">GET</span>
                        <span>/api/users</span> - List users (paginated)
                    </div>
                    <div class="endpoint">
                        <span class="method post">POST</span>
                        <span>/api/users</span> - Create new user
                    </div>
                    <div class="endpoint">
                        <span class="method get">GET</span>
                        <span>/api/teams</span> - List teams
                    </div>
                    <div class="endpoint">
                        <span class="method post">POST</span>
                        <span>/api/teams</span> - Create new team
                    </div>
                    <div class="endpoint">
                        <span class="method get">GET</span>
                        <span>/api/roles</span> - List available roles
                    </div>
                    <div class="endpoint">
                        <span class="method post">POST</span>
                        <span>/api/auth/login</span> - User authentication
                    </div>
                    <div class="endpoint">
                        <span class="method post">POST</span>
                        <span>/api/auth/logout</span> - User logout
                    </div>
                </div>
            </section>

            <section class="section">
                <h2>Key Features</h2>
                <ul class="feature-list">
                    <li>Async/await patterns throughout for optimal performance</li>
                    <li>Connection pooling with AsyncpgPoolConfig</li>
                    <li>Automatic OpenAPI documentation generation</li>
                    <li>CORS and CSRF protection middleware</li>
                    <li>Structured logging with request correlation</li>
                    <li>Database migrations with version control</li>
                    <li>Comprehensive test coverage with pytest</li>
                    <li>Type checking with mypy and pyright</li>
                </ul>
            </section>

            <section class="section">
                <h2>Getting Started</h2>
                <div class="code-block">
                    <pre># Install dependencies
make install

# Start infrastructure (PostgreSQL, Redis)
make start-infra

# Run the application
uv run litestar run

# Run tests
make test

# Check code quality
make lint</pre>
                </div>
            </section>
        </div>

        <footer>
            <p>Built with ❤️ using Litestar and SQLSpec</p>
            <p>© 2024 SQLStack Reference Architecture</p>
        </footer>
    </div>
</body>
</html>
"""
        return Response(content=html_content, status_code=HTTP_200_OK, media_type=MediaType.HTML)
