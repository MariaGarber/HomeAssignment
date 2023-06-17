from kubernetes import client, config
import yaml
import jenkins
from kubernetes.stream import stream
import time


def create_namespace(core_api, namespace):
    """
    Create new namespace in kubernetes
    :param core_api: core api client
    :param namespace: desired namespace
    :return: nothing
    """
    namespace_obj = client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace))
    try:
        core_api.create_namespace(namespace_obj)
        print("Namespace created successfully.")
    except client.rest.ApiException as e:
        if e.status == 409:
            print("Namespace already exists.")
        else:
            print("Error creating namespace:", e)


def create_deployment(apps_api, namespace, yaml_content):
    """
    Create new kubernetes deployment
    :param apps_api: apps api client
    :param namespace: namespace where the deployment should be created
    :param yaml_content: yaml of the deployment
    :return: nothing
    """
    apps_api.create_namespaced_deployment(
        body=yaml_content,
        namespace=namespace
    )
    print("Deployment created successfully.")


def create_service(core_api, namespace, yaml_content):
    """
    Create new kubernetes service
    :param core_api: core api client
    :param namespace: namespace where the service should be created
    :param yaml_content: yaml of the service
    :return: nothing
    """
    core_api.create_namespaced_service(
        body=yaml_content,
        namespace=namespace
    )
    print("Service created successfully.")


def get_jenkins_credentials(core_api, namespace):
    """
    Get credentials of running jenkins
    :param core_api: core api client
    :param namespace: namespace where the jenkins service running
    :return: username and password
    """
    pods = core_api.list_namespaced_pod(namespace=namespace, label_selector="app=jenkins")
    if not pods.items:
        print("Jenkins pod not found.")
        return

    jenkins_pod = pods.items[0]

    command = ["/bin/cat", "/var/jenkins_home/secrets/initialAdminPassword"]
    resp = stream(
        core_api.connect_get_namespaced_pod_exec,
        name=jenkins_pod.metadata.name,
        namespace=jenkins_pod.metadata.namespace,
        command=command,
        stderr=True,
        stdin=False,
        stdout=True,
        tty=False,
    )

    admin_password = resp.strip()
    admin_username = "admin"

    return admin_username, admin_password


def main():
    # Configurations
    config.load_kube_config()
    api_client = client.ApiClient()
    apps_api = client.AppsV1Api(api_client)
    core_api = client.CoreV1Api(api_client)

    # Create namespace
    namespace = 'devops'
    create_namespace(core_api, namespace)

    # Read deployment yaml and apply
    with open('jenkins-deployment.yaml', 'r') as f:
        yaml_content = f.read()
    deployment_yaml = yaml.safe_load(yaml_content)
    create_deployment(apps_api, namespace, deployment_yaml)

    # Read service yaml and apply
    with open('jenkins-service.yaml', 'r') as f:
        yaml_content = f.read()
    service_yaml = yaml.safe_load(yaml_content)
    create_service(core_api, namespace, service_yaml)

    # Wait for Jenkins service to run
    print('Waiting 30 sec for jenkins service')
    time.sleep(30)

    # Connect to Jenkins
    jenkins_url = "http://localhost:8080"

    # Get the Jenkins admin username and password
    admin_username, admin_password = get_jenkins_credentials(core_api, namespace)

    print("Admin Username:", admin_username)
    print("Admin Password:", admin_password)

    server = jenkins.Jenkins(jenkins_url, username=admin_username, password=admin_password)

    # Read configuration file to connect to git
    with open('connect-to-git.xml', 'r') as f:
        config_xml = f.read()
    server.create_job("connect-to-git", config_xml)
    server.enable_job("connect-to-git")


if __name__ == '__main__':
    main()
