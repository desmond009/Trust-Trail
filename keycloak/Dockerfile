# Stage 1: build the strip-sid protocol mapper (the only custom Java in TrustTrail).
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /src
COPY strip-sid-mapper/pom.xml .
RUN mvn -q -B dependency:go-offline
COPY strip-sid-mapper/src ./src
RUN mvn -q -B package

# Stage 2: stock Keycloak plus the provider jar.
FROM quay.io/keycloak/keycloak:26.8.1
COPY --from=build /src/target/strip-sid-mapper-1.0.0.jar /opt/keycloak/providers/
