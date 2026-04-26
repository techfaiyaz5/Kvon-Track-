pipeline {
    agent any

    environment {
        // 1. Apna DockerHub username yahan likho (Jaise: techfaiyaz5)
        DOCKER_HUB_USER = 'techfaiyaz5' 
        APP_NAME = 'kvontrack-gemini'
        IMAGE_TAG = "${env.BUILD_NUMBER}"
    }

    stages {
        stage('Checkout Code') {
            steps {
                checkout scm
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    echo "Building Docker Image..."
                    sh "docker build -t ${DOCKER_HUB_USER}/${APP_NAME}:${IMAGE_TAG} ."
                    sh "docker tag ${DOCKER_HUB_USER}/${APP_NAME}:${IMAGE_TAG} ${DOCKER_HUB_USER}/${APP_NAME}:latest"
                }
            }
        }

        stage('Push to Docker Hub') {
            steps {
                script {
                    echo "Pushing Image to Docker Hub..."
                    // YAHAN UPDATE KIYA HAI: 'docker-hub-creds' (Aapki screenshot ke hisaab se)
                    withCredentials([usernamePassword(credentialsId: 'docker-hub-creds', passwordVariable: 'DOCKER_PASS', usernameVariable: 'DOCKER_USER')]) {
                        sh "echo ${DOCKER_PASS} | docker login -u ${DOCKER_USER} --password-stdin"
                        sh "docker push ${DOCKER_HUB_USER}/${APP_NAME}:${IMAGE_TAG}"
                        sh "docker push ${DOCKER_HUB_USER}/${APP_NAME}:latest"
                    }
                }
            }
        }

        stage('Update K8s Manifest') {
            steps {
                script {
                    echo "Updating Deployment YAML with new Tag..."
                                        
                    // Note: Ensure 'github-creds' is also created in Jenkins like docker-hub-creds
                    withCredentials([usernamePassword(credentialsId: 'github-creds', passwordVariable: 'GIT_PASS', usernameVariable: 'GIT_USER')]) {
                        sh "git config user.email 'jenkins@example.com'"
                        sh "git config user.name 'Jenkins CI'"
    
                        // 1. Forcefully GitHub se latest changes uthao aur merge karo
                        sh "git fetch origin testing"
                        sh "git reset --hard origin/testing"
    
                         // 2. Ab apni sed command chalao
                        sh "sed -i 's|image: ${DOCKER_HUB_USER}/${APP_NAME}:.*|image: ${DOCKER_HUB_USER}/${APP_NAME}:${IMAGE_TAG}|g' k8s/main.yaml"
    
                        // 3. Add aur Commit (|| true lagao taaki 'nothing to commit' par build fail na ho)
                         sh "git add k8s/main.yaml"
                         sh "git commit -m 'Update image tag to ${env.BUILD_NUMBER}' || echo 'No changes to commit'"
    
                        // 4. Force Push taaki Diverge wala jhamela hi khatam ho jaye
                        sh "git push https://${GIT_USER}:${GIT_PASS}@github.com/techfaiyaz5/Kvon-Track-.git HEAD:testing -f"
                    }
                }
            }
        }
    }
}