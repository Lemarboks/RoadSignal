FROM redis:7.4.5-alpine
COPY --chmod=0555 entrypoint.sh /usr/local/bin/saferoute-redis-entrypoint
ENTRYPOINT ["saferoute-redis-entrypoint"]
CMD ["redis-server", "/tmp/redis.conf"]
