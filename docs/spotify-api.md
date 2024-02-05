
## Spotify API
#### Get user ID
```sh
$ http https://api.spotify.com/v1/me "Authorization: Bearer ${ACCESS_TOKEN}"
```

#### Get playlists
```sh
$ http https://api.spotify.com/v1/me/playlists "Authorization: Bearer ${ACCESS_TOKEN}"
    | jq '.items[] | "\(.id) \(.name)"'
```