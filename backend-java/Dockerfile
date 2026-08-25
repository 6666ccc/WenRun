FROM maven:3.9-eclipse-temurin-21 AS build

WORKDIR /build

COPY pom.xml ./
RUN mvn -B dependency:go-offline

COPY src ./src
RUN cp src/main/resources/application.yml.example src/main/resources/application.yml
RUN mvn -B -DskipTests package


FROM eclipse-temurin:21-jre

ENV LANG=C.UTF-8
WORKDIR /app

COPY --from=build /build/target/backend-java-0.0.1-SNAPSHOT.jar app.jar

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "/app/app.jar"]
