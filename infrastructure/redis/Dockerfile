FROM redis:7.4.5-alpine
USER redis
COPY --chmod=0555 entrypoint.sh /usr/local/bin/roadsignal-redis-entrypoint
ENTRYPOINT ["roadsignal-redis-entrypoint"]
CMD ["redis-server", "/tmp/redis.conf"]
