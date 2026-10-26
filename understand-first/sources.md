# Source map

Where to look a concept up when the work reaches it. This is not a syllabus: look up only what the current work touches, prefer primary sources, and cross-check with blogs only when needed. The learner's own additions live in `sources-added.md` in the data directory.

### Software design
- [Martin Fowler's articles](https://martinfowler.com/tags/): design principles, architecture and practices explained by topic.

### Object-oriented design and patterns
- [Refactoring Guru patterns catalog](https://refactoring.guru/design-patterns/catalog): the classic creational, structural and behavioral patterns, each with its own page.
- [Evans' DDD Reference](https://www.domainlanguage.com/ddd/reference/): entities, value objects, aggregates, repositories and domain events.

### Code-level concepts
- [Fowler's refactoring catalog](https://refactoring.com/catalog/): named, step-by-step code changes and the smells they fix.
- The language's own official manual, looked up for the language in the ledger's code dial.

### Data and databases
- [PostgreSQL documentation](https://www.postgresql.org/docs/current/): transactions, isolation, indexes and constraints, with exact behavior.
- [Use The Index, Luke](https://use-the-index-luke.com/): how indexes work and how queries use them.

### Distributed systems and reliability
- [Azure cloud design patterns](https://learn.microsoft.com/en-us/azure/architecture/patterns/): retry, circuit breaker, bulkhead, idempotent consumer, saga and more, each with problem and trade-offs.
- [Azure antipatterns](https://learn.microsoft.com/en-us/azure/architecture/antipatterns/): common designs that degrade under load.
- [AWS Builders' Library](https://aws.amazon.com/builders-library/): how large systems handle timeouts, retries and failure.

### Messaging and async work
- [Enterprise Integration Patterns](https://www.enterpriseintegrationpatterns.com/patterns/messaging/): messaging vocabulary and patterns.
- [Azure cloud design patterns](https://learn.microsoft.com/en-us/azure/architecture/patterns/): queue-based load leveling, competing consumers, publisher-subscriber.

### System design and scale
- [Azure Well-Architected guide](https://learn.microsoft.com/en-us/azure/well-architected/): reliability, performance, security, cost and operations trade-offs.
- [AWS Builders' Library](https://aws.amazon.com/builders-library/)
- [Google SRE books](https://sre.google/books/): reliability, load and operating large services.

### Build, delivery and deployment
- [DORA capabilities](https://dora.dev/capabilities/): continuous integration, continuous delivery, trunk-based development and what they measure.
- [continuousdelivery.com](https://continuousdelivery.com/): deployment pipelines and release practices.
- [The Twelve-Factor App](https://12factor.net/): build, release and run separation, config, dependencies and processes.

### The runtime stack
- [MDN HTTP documentation](https://developer.mozilla.org/en-US/docs/Web/HTTP): requests, responses, caching and headers.
- [Docker overview](https://docs.docker.com/get-started/docker-overview/): images, containers and what they isolate.
- [The Twelve-Factor App](https://12factor.net/)

### Security
- [OWASP Top 10](https://top10.owasp.org/): the current list of the most common web risks; check which edition is current.
- [OWASP cheat sheets](https://cheatsheetseries.owasp.org/): practical guidance by topic.
- [OAuth 2](https://oauth.net/2/) and [RFC 6749](https://www.rfc-editor.org/rfc/rfc6749): delegated authorization, tokens and scopes.

### Observability and operations
- [OpenTelemetry concepts](https://opentelemetry.io/docs/concepts/): logs, metrics, traces and how they connect.
- [Google SRE books](https://sre.google/books/): SLIs, SLOs, error budgets and alerting.

### Testing
- [Fowler's test pyramid](https://martinfowler.com/bliki/TestPyramid.html): layers of tests and the trade-off between speed and confidence.
