package cache

import (
	"sync"
	"time"
)

// Cache is a concurrency-safe string cache.
type Cache struct {
	mu    sync.Mutex
	items map[string]string
}

func New() *Cache { return &Cache{items: map[string]string{}} }

func (c *Cache) Get(key string) (string, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	v, ok := c.items[key]
	return v, ok
}

func (c *Cache) Set(key, value string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.items[key] = value
}

// GetOrLoad returns the cached value or loads, stores and returns it.
func (c *Cache) GetOrLoad(key string, load func() string) string {
	if v, ok := c.items[key]; ok {
		return v
	}
	v := load()
	c.items[key] = v
	return v
}

// RefreshEvery reloads key in the background at the given interval.
func (c *Cache) RefreshEvery(key string, every time.Duration, load func() string) {
	go func() {
		for range time.Tick(every) {
			c.items[key] = load()
		}
	}()
}
