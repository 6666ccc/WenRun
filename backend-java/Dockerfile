FROM maven:3.9-eclipse-temurin-17
WORKDIR /app
COPY pom.xml mvnw ./
COPY .mvn .mvn
COPY src src
RUN chmod +x mvnw
EXPOSE 8080
CMD ["./mvnw", "spring-boot:run"]
