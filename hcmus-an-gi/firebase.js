import { initializeApp } from "firebase/app";

const firebaseConfig = {
    apiKey: "AIzaSy...", // Thay bằng chuỗi của bạn
    authDomain: "://firebaseapp.com",
    projectId: "ct-project-ad2c7-9c9cc",
    storageBucket: "ct-project-ad2c7-9c9cc.firebasestorage.app",
    messagingSenderId: "75032248216",
    appId: "1:75032248216:web:dd74c1a142fc52a60d35ed",
    measurementId: "G-VR6Z62QTP3"
};

// Khởi tạo Firebase
const app = initializeApp(firebaseConfig);
export default app;
