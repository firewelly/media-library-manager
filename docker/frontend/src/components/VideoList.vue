<template>
  <div class="video-list">
    <div class="search-bar">
      <input 
        v-model="searchQuery" 
        @keyup.enter="fetchVideos" 
        placeholder="Search videos..."
      >
      <button @click="fetchVideos">Search</button>
    </div>

    <div v-if="loading" class="loading">Loading...</div>
    
    <div v-else class="grid">
      <div v-for="video in videos" :key="video.id" class="card">
        <div class="card-content">
          <h3>{{ video.title || video.file_name }}</h3>
          <p class="meta">
            <span v-if="video.year">{{ video.year }}</span>
            <span v-if="video.stars"> | {{ video.stars }} Stars</span>
          </p>
          <div class="tags" v-if="video.tags">
            <span v-for="tag in video.tags.split(',')" :key="tag" class="tag">
              {{ tag.trim() }}
            </span>
          </div>
        </div>
      </div>
    </div>
    
    <div class="pagination">
      <button :disabled="page === 1" @click="changePage(-1)">Prev</button>
      <span>Page {{ page }}</span>
      <button @click="changePage(1)">Next</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const videos = ref([])
const loading = ref(false)
const searchQuery = ref('')
const page = ref(1)
const limit = 20

// Use relative path for API which will be proxied by Nginx
const API_URL = '' 

const fetchVideos = async () => {
  loading.value = true
  try {
    const skip = (page.value - 1) * limit
    const params = { skip, limit }
    if (searchQuery.value) {
      params.search = searchQuery.value
    }
    const response = await axios.get(`${API_URL}/videos/`, { params })
    videos.value = response.data
  } catch (error) {
    console.error('Error fetching videos:', error)
  } finally {
    loading.value = false
  }
}

const changePage = (delta) => {
  page.value += delta
  fetchVideos()
}

onMounted(() => {
  fetchVideos()
})
</script>

<style scoped>
.search-bar {
  margin-bottom: 20px;
  display: flex;
  gap: 10px;
}
input {
  flex: 1;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
}
button {
  padding: 10px 20px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
button:disabled {
  background-color: #ccc;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}
.card {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.1);
  overflow: hidden;
}
.card-content {
  padding: 15px;
}
.meta {
  color: #666;
  font-size: 0.9em;
}
.tags {
  margin-top: 10px;
}
.tag {
  background: #eee;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.8em;
  margin-right: 5px;
}
.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: center;
  gap: 10px;
  align-items: center;
}
</style>
