from locust import HttpUser, task, between

class LinkShortenerUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Создаём ссылку для последующих тестов редиректа.
        response = self.client.post("/api/links/shorten", json={"original_url": "https://locust.io"})
        if response.status_code in (200, 201):
            data = response.json()
            self.short_code = data.get("short_code")
        else:
            self.short_code = None

    @task(2)
    def create_link(self):
        self.client.post("/api/links/shorten", json={"original_url": "https://example.com/test"})

    @task(5)
    def redirect_link(self):
        if self.short_code:
            self.client.get(f"/api/links/{self.short_code}", allow_redirects=False)