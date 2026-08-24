pipeline {
    agent any

    environment {
        // -- Sirf ye check karein ki naam sahi hain --
        DOCKERHUB_USERNAME = 'techfaiyaz5' 
        APP_NAME           = 'kvontrack'
        DOCKERHUB_CREDS    = 'dockerhub-creds' // Jo ID aapne Jenkins me di thi
        
        // -- Automatic Variables --
        IMAGE_TAG          = "${env.BUILD_NUMBER}"
        FULL_IMAGE         = "${DOCKERHUB_USERNAME}/${APP_NAME}:${IMAGE_TAG}"
    }

    stages {
        stage('1. Checkout Code') {
            steps {
                echo "📥 GitHub se code pull ho raha hai..."
                checkout scm
            }
        }

        stage('2. Build Docker Image') {
            steps {
                echo "🐳 Docker Image ban rahi hai..."
                sh "docker build -t ${FULL_IMAGE} ."
                sh "docker tag ${FULL_IMAGE} ${DOCKERHUB_USERNAME}/${APP_NAME}:latest"
            }
        }

        stage('3. Push to Docker Hub') {
            steps {
                echo "📤 Docker Hub par image push ho rahi hai..."
                withCredentials([usernamePassword(credentialsId: "${DOCKERHUB_CREDS}", passwordVariable: 'DOCKER_PASS', usernameVariable: 'DOCKER_USER')]) {
                    sh "echo \$DOCKER_PASS | docker login -u \$DOCKER_USER --password-stdin"
                    sh "docker push ${FULL_IMAGE}"
                    sh "docker push ${DOCKERHUB_USERNAME}/${APP_NAME}:latest"
                }
            }
        }

        stage('4. Deploy to Local Kubernetess') {
            steps {
                echo "🚀 EC2 Server par app live ho raha hai...."
                // K8s file me naya image tag update karo
                sh "sed -i 's|image: .*|image: ${FULL_IMAGE}|g' k8s/main.yaml"
                
                // Kubernetes cluster me deploy karo
                sh "kubectl apply -f k8s/main.yaml"
            }
        }
    }

    post {
        success {
            echo "🎉 MUBARAK HO. KvonTrack App Deploy Ho Gaya Hai! 🚀"
        }
        always {
            echo "🧹 Space bachane ke liye purani images clean ho rahi hain..."
            sh "docker logout"
            sh "docker rmi ${FULL_IMAGE} || true"
        }
    }
}