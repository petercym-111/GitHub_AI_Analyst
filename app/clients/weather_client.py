import httpx

class WeatherClient:

    async def get_coordinates(
        self,
        location: str
    ):

        # Open-Meteo forecasts need coordinates, so the first request converts
        # the user-friendly place name into the provider's required format.
        async with httpx.AsyncClient() as client:

            response = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={
                    "name": location,
                    "count": 1
                }
            )

            response.raise_for_status()
            data = response.json()
            if not data.get("results"):
                raise ValueError("Location not found")

            # `count=1` chooses the provider's top match.  This is concise for
            # an MVP but can select the wrong city; production UX should handle
            # ambiguous or empty `results` explicitly.
            result = data["results"][0]

            return {
                "latitude": result["latitude"],
                "longitude": result["longitude"]
            }

    async def get_weather(
        self,
        location: str,
        units: str
    ):

        # The tool contract uses friendly units; normalize them at the provider
        # boundary rather than leaking provider-specific values to the schema.
        coordinates = await self.get_coordinates(
            location
        )

        temperature_unit = (
            "fahrenheit"
            if units == "fahrenheit"
            else "celsius"
        )

        # Per-request clients are simple and close resources automatically. At
        # meaningful traffic, inject a shared AsyncClient at app lifespan to
        # reuse its connection pool.
        async with httpx.AsyncClient() as client:

            response = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": coordinates["latitude"],
                    "longitude": coordinates["longitude"],
                    "current_weather": True,
                    "temperature_unit": temperature_unit
                }
            )

            response.raise_for_status()
            data = response.json()

            # Return a stable, small domain payload instead of the entire API
            # response; this reduces coupling and limits model interpretation.
            return {
                "location": location,
                "temperature": data["current_weather"]["temperature"],
                "unit": units
            }
