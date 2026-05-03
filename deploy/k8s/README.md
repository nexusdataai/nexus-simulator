# Kubernetes deployment — nexus-simulator

Production-shaped manifests for deploying the reference server as an
independent pod in EKS.

## Conventions

| What | Value |
|------|-------|
| Namespace                | `nexus-simulator` (single, fixed)                                  |
| ServiceAccount           | `simulator-role-sa` (single, fixed)                                |
| IAM role assumed via IRSA| `simulator-role` (created once by admin)                           |
| S3 buckets               | `simulator-wxcc-${ENV}`, `simulator-sfdc-${ENV}`, `simulator-oracle-erp-${ENV}`, `simulator-sap-${ENV}`, `simulator-external-${ENV}` |
| Image (production)       | `${ECR_REGISTRY}/nexus-simulator:<git-sha>` or `:latest`            |
| Image (in-pod tests)     | `${ECR_REGISTRY}/nexus-simulator:<git-sha>-test` or `:latest-test`  |

## How to apply

The recommended path is via the deploy script:

```bash
cd /opt/mycode/nexus/nexus-simulator
./deploy/deploy-and-test.sh --env dev --region us-east-1
```

Direct apply (advanced):

```bash
# Substitute placeholders, then apply
ENV=dev
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY=${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com
IMAGE_TAG=$(git rev-parse --short HEAD)

mkdir -p /tmp/simulator-k8s
cp deploy/k8s/*.yaml /tmp/simulator-k8s/
sed -i "s|\${ENV}|${ENV}|g; \
        s|\${REGION}|us-east-1|g; \
        s|REPLACE_WITH_ECR_REGISTRY|${ECR_REGISTRY}|g; \
        s|REPLACE_WITH_IAM_ROLE_ARN|arn:aws:iam::${ACCOUNT_ID}:role/simulator-role|g" \
    /tmp/simulator-k8s/*.yaml

kubectl apply -k /tmp/simulator-k8s/
kubectl -n nexus-simulator rollout status deploy/nexus-simulator
```

## Prerequisite — admin-side setup (one time)

Before any deploy can succeed, an AWS administrator must run:

```bash
./deploy/admin/setup-admin-role.sh --region <region>
```

That creates:

- IAM role **`simulator-role`** with permissions on
  `simulator-*` resources (S3 buckets per plugin, plus DynamoDB and SSM).
- IAM trust policy that lets `system:serviceaccount:nexus-simulator:simulator-role-sa`
  assume the role via IRSA.
- VPC endpoints (s3, dynamodb, sts, ssm, ssm-messages, ec2, ecr.api,
  ecr.dkr, secretsmanager, logs, glue, athena, events, eks)
  in the cluster's VPC so the pod can reach AWS services privately.

See [../iam/README.md](../iam/README.md) for full admin instructions.

## What you must replace before applying

| Placeholder | Replacement | Patched by |
|-------------|-------------|------------|
| `${ENV}`                       | `dev` / `stage` / `prod`                              | deploy-and-test.sh |
| `${REGION}`                    | AWS region (e.g. `us-east-1`, `ap-southeast-1`)        | deploy-and-test.sh |
| `REPLACE_WITH_ECR_REGISTRY`    | e.g. `123456789012.dkr.ecr.us-east-1.amazonaws.com`    | deploy-and-test.sh |
| `REPLACE_WITH_IAM_ROLE_ARN`    | `arn:aws:iam::<account>:role/simulator-role`           | deploy-and-test.sh |

## Files

- [namespace.yaml](namespace.yaml) — creates `nexus-simulator` namespace.
- [serviceaccount.yaml](serviceaccount.yaml) — `simulator-role-sa` with IRSA annotation placeholder.
- [configmap.yaml](configmap.yaml) — non-secret `SimulatorConfig` values; `${ENV}` and `${REGION}` patched at apply time.
- [deployment.yaml](deployment.yaml) — 2 replicas, probes on `/health` + `/readiness`, `readOnlyRootFilesystem`, drop ALL caps, topology spread; `tmp` and `reports` emptyDir volumes (the `reports` volume backs `make test-bdd` HTML output).
- [service.yaml](service.yaml) — ClusterIP on port 8000.
- [hpa.yaml](hpa.yaml) — CPU/memory autoscaler 2 → 10.
- [networkpolicy.yaml](networkpolicy.yaml) — deny-all ingress, allow from kube-system + same-app pods.
- [kustomization.yaml](kustomization.yaml) — wires everything together; `kubectl apply -k`.

No Ingress is shipped — ALB annotations are environment-specific. Add an
overlay in [nexus-deployer](../../../nexus-deployer/) per cluster.

## Verify after deploy

```bash
kubectl -n nexus-simulator get all
kubectl -n nexus-simulator port-forward svc/nexus-simulator 8000:8000 &
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/readiness
curl -fsS http://localhost:8000/version
```

## Run tests inside the pod

When deployed with the test image (`:<sha>-test`), every test tier is
runnable via `kubectl exec`:

```bash
POD=$(kubectl -n nexus-simulator get pod -l app.kubernetes.io/name=nexus-simulator -o jsonpath='{.items[0].metadata.name}')

kubectl -n nexus-simulator exec -it "$POD" -- make test-unit
kubectl -n nexus-simulator exec -it "$POD" -- make test-integration
kubectl -n nexus-simulator exec -it "$POD" -- make test-e2e
kubectl -n nexus-simulator exec -it "$POD" -- make test-journeys
kubectl -n nexus-simulator exec -it "$POD" -- make test-bdd
kubectl -n nexus-simulator exec -it "$POD" -- make test-endurance
```

`./deploy/deploy-and-test.sh` runs all tiers in sequence and aggregates
results — see its `--help` for options.
