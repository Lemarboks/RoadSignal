# Reuse the already installed CPU PyTorch/Transformers layers.
FROM roadsignal-retrieval:local
USER root
COPY requirements.txt /service/verification-requirements.txt
RUN pip install --no-cache-dir -r /service/verification-requirements.txt \
    && pip install --no-cache-dir --no-deps supervision==0.27.0
COPY server.py smoke.py /service/
ENV MODEL_ROLE=verification OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLCONFIGDIR=/tmp/matplotlib
USER 10001:10001
EXPOSE 8080
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080", "--limit-concurrency", "4", "--no-access-log"]
