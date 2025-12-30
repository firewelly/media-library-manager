<template>
  <div class="container">
    <header>
      <h1>Media Library</h1>
    </header>
    <main>
      <VideoList />
    </main>
  </div>
</template>

<script setup>
import VideoList from './components/VideoList.vue'
</script>

<style>
body {
  font-family: Arial, sans-serif;
  margin: 0;
  padding: 0;
  background-color: #f5f5f5;
}
.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}
header {
  background-color: #333;
  color: white;
  padding: 10px 20px;
  margin-bottom: 20px;
  border-radius: 5px;
}
</style>
