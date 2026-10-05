FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /app
COPY backend-java/pom.xml ./
RUN mvn -B dependency:go-offline
COPY backend-java/src ./src
# Local credentials are excluded from the context; the example is the baseline.
RUN cp src/main/resources/application.yml.example src/main/resources/application.yml && mvn -B -DskipTests package

FROM eclipse-temurin:21-jre-jammy
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/* && useradd --uid 10001 --create-home app
WORKDIR /app
COPY --from=build /app/target/backend-java-0.0.1-SNAPSHOT.jar app.jar
USER 10001
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
HEALTHCHECK --interval=30s --timeout=8s --start-period=90s CMD curl -fsS http://127.0.0.1:8080/api/health/ready >/dev/null || exit 1
