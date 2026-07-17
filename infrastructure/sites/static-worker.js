export default {
  async fetch(request, environment) {
    if (!environment.ASSETS) {
      return new Response("SafeRoute web assets are unavailable", { status: 503 });
    }
    return environment.ASSETS.fetch(request);
  },
};
