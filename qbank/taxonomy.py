"""Topic -> subtopics tree that drives LLM expansion.

Each (topic, subtopic) pair is one generation prompt, so the number of
subtopics x questions-per-prompt sets how big the bank gets. Subtopics are
deliberately concrete ("HashMap internals", "volatile vs synchronized")
rather than broad, so generated questions stay specific and dedupe well.
"""
from __future__ import annotations

TAXONOMY: dict[str, list[str]] = {
    "OOP": [
        "encapsulation and access modifiers", "inheritance vs composition",
        "polymorphism and dynamic dispatch", "abstraction, interfaces vs abstract classes",
        "constructors, constructor chaining, initialization order",
        "method overloading vs overriding rules", "the Object class contract",
        "SOLID principles applied to Java", "coupling, cohesion, encapsulation of state",
        "final classes/methods/fields and immutability by design",
    ],
    "Java Core": [
        "String, StringBuilder, StringBuffer and the string pool",
        "equals() and hashCode() contract", "checked vs unchecked exceptions and best practices",
        "try-with-resources and AutoCloseable", "generics, bounded types, wildcards, type erasure",
        "enums and enum-backed patterns", "autoboxing/unboxing pitfalls",
        "pass-by-value semantics", "static vs instance, static initializers",
        "annotations and retention policies", "reflection and its costs",
        "serialization, transient, serialVersionUID", "records and sealed classes",
        "nested, inner, local and anonymous classes",
    ],
    "Java Collections": [
        "ArrayList vs LinkedList trade-offs", "HashMap internals: buckets, resize, treeify",
        "HashSet/LinkedHashSet/TreeSet differences", "Comparable vs Comparator",
        "fail-fast vs fail-safe iterators", "Queue, Deque, PriorityQueue",
        "Map iteration and ordering guarantees", "Collections utility methods and views",
        "Iterator and ListIterator", "load factor, capacity, hash distribution",
    ],
    "Spring": [
        "IoC container and dependency injection styles", "bean scopes and lifecycle callbacks",
        "@Component vs @Bean vs @Configuration", "Spring Boot auto-configuration",
        "@Transactional propagation and isolation", "Spring MVC request lifecycle",
        "REST controllers, ResponseEntity, exception handling", "Spring Data JPA repositories",
        "profiles, properties, @ConfigurationProperties", "AOP, proxies, and self-invocation",
        "Actuator, health checks, metrics",
    ],
    "JVM": [
        "class loading phases and classloader hierarchy", "runtime memory areas: heap, stack, metaspace",
        "garbage collectors: G1, ZGC, generational model", "JIT compilation and warmup",
        "the Java Memory Model: happens-before, visibility", "OutOfMemoryError causes and diagnosis",
        "escape analysis and scalar replacement", "reference types: soft/weak/phantom",
        "stack traces, stack frames, tail calls", "bytecode basics and javap",
    ],
    "Multithreading": [
        "Thread lifecycle, start vs run", "synchronized, monitors, intrinsic locks",
        "volatile vs synchronized", "wait/notify and guarded blocks",
        "ExecutorService, thread pools, sizing", "CompletableFuture composition",
        "ConcurrentHashMap and concurrent collections", "locks: ReentrantLock, ReadWriteLock, StampedLock",
        "atomics and CAS", "deadlock, livelock, starvation", "ThreadLocal use and leaks",
        "CountDownLatch, CyclicBarrier, Semaphore, Phaser", "ForkJoinPool and work stealing",
    ],
    "Databases": [
        "JDBC basics, PreparedStatement, batching", "transactions and ACID",
        "isolation levels and read phenomena", "indexes: B-tree, covering, selectivity",
        "normalization vs denormalization", "joins and query planning",
        "connection pooling (HikariCP)", "the N+1 query problem with ORMs",
        "optimistic vs pessimistic locking", "SQL vs NoSQL trade-offs",
    ],
    "Java 8": [
        "lambdas and functional interfaces", "Stream API: intermediate vs terminal ops",
        "Collectors and downstream collectors", "Optional: correct use and anti-patterns",
        "method references, the four kinds", "default and static interface methods",
        "parallel streams: when they help and hurt", "the java.time API",
        "Function/Predicate/Supplier/Consumer composition", "reduce, flatMap, grouping",
    ],
    "Patterns": [
        "Singleton: variants, thread safety, downsides", "Factory and Abstract Factory",
        "Builder for complex construction", "Strategy and Template Method",
        "Observer and event handling", "Decorator vs inheritance",
        "Adapter, Facade, Proxy", "Dependency Inversion and testable design",
        "immutability and value objects", "anti-patterns: God object, service locator",
    ],
    "Testing": [
        "JUnit 5 lifecycle and assertions", "test doubles: stub, mock, spy, fake",
        "Mockito: stubbing, verification, argument captors", "unit vs integration vs e2e",
        "the test pyramid and where logic belongs", "TDD red-green-refactor",
        "testing concurrency and time", "parameterized and property-based tests",
        "code coverage: value and misuse", "testing Spring slices (@WebMvcTest, @DataJpaTest)",
    ],
}
