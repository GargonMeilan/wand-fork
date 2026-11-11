#!/bin/sh
# Tests only throwaway containers; does not start Wand or touch its data mounts.
set -eu
docker build -t wand-ruffle-web-test web
for scenario in domains paths shared flash captcha; do
    play=http://old.example.test
    media=http://legacy.example.test
    player=ruffle
    captcha=
    case "$scenario" in
        paths) play=http://old.example.test/game; media=http://legacy.example.test/assets ;;
        shared) play=http://old.example.test/game; media=http://old.example.test/media ;;
        flash) player=flash ;;
        captcha) captcha=example-site-key ;;
    esac
    docker run --rm --add-host dash:127.0.0.1 \
        -e WEB_LEGACY_PLAY="$play" -e WEB_LEGACY_MEDIA="$media" \
        -e GAME_ADDRESS=game.example.test -e GAME_LOGIN_PORT=7112 \
        -e LEGACY_PLAYER="$player" -e WEB_RECAPTCHA_SITE="$captcha" \
        -v "$(pwd)/templates:/t:ro" --entrypoint sh wand-ruffle-web-test -ec '
            rm /etc/nginx/conf.d/default.conf
            mkdir -p /usr/share/nginx/legacy/media/play/v2/client /usr/share/nginx/legacy/play
            echo bootstrap > /usr/share/nginx/legacy/media/play/v2/client/load.swf
            echo boots > /usr/share/nginx/legacy/media/boots.swf
            dockerize -template /t/sites/legacy.conf.template:/etc/nginx/conf.d/legacy.conf
            for locale in en es fr pt; do
                source=/t/legacy-media/play/$locale/index.html.template
                [ "$locale" != en ] || source=/t/legacy-media/play/index.html.template
                mkdir -p /usr/share/nginx/legacy/play/$locale
                dockerize -template "$source:/usr/share/nginx/legacy/play/$locale/index.html"
            done
            cp /usr/share/nginx/legacy/play/en/index.html /usr/share/nginx/legacy/play/index.html
            nginx -t
            nginx
            playhost=$(echo "$WEB_LEGACY_PLAY" | cut -d/ -f3)
            mediahost=$(echo "$WEB_LEGACY_MEDIA" | cut -d/ -f3)
            playpath=$(echo "$WEB_LEGACY_PLAY" | cut -d/ -f4-)
            mediapath=$(echo "$WEB_LEGACY_MEDIA" | cut -d/ -f4-)
            wget -qO /tmp/page --header="Host: $playhost" "http://127.0.0.1/${playpath:+$playpath/}"
            if [ "$LEGACY_PLAYER" = flash ]; then grep -q "<object " /tmp/page; else grep -q "id=\"wand-game\"" /tmp/page; fi
            wget -qO- --header="Host: $mediahost" "http://127.0.0.1/${mediapath:+$mediapath/}boots.swf" | grep -q boots
            wget -qO- --header="Host: $mediahost" http://127.0.0.1/play/v2/client/load.swf | grep -q bootstrap
            wget -qO- --header="Host: $playhost" http://127.0.0.1/__wand/ruffle/ruffle.js > /dev/null
            wasm=$(basename "$(find /opt/wand/ruffle -name "*.wasm" | head -1)")
            wget -SO /dev/null --header="Host: $playhost" "http://127.0.0.1/__wand/ruffle/$wasm" 2>&1 | grep -qi "Content-Type: application/wasm"
        '
done
