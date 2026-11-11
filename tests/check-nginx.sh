#!/bin/sh
# Tests only throwaway containers; does not start Wand or touch its data mounts.
set -eu
docker build -t wand-ruffle-web-test web
for scenario in domains paths shared flash captcha; do
    play=http://old.example.test
    media=http://legacy.example.test
    vanilla_play=http://play.example.test
    vanilla_media=http://media.example.test
    player=ruffle
    captcha=
    case "$scenario" in
        paths) play=http://old.example.test/game; media=http://legacy.example.test/assets ;;
        shared) play=http://old.example.test/game; media=http://old.example.test/media ;;
        flash) player=flash ;;
        captcha) captcha=example-site-key ;;
    esac
    case "$scenario" in
        paths) vanilla_play=http://play.example.test/game; vanilla_media=http://media.example.test/assets ;;
        shared) vanilla_play=http://play.example.test/game; vanilla_media=http://play.example.test/media ;;
    esac
    docker run --rm --add-host dash:127.0.0.1 \
        -e WEB_LEGACY_PLAY="$play" -e WEB_LEGACY_MEDIA="$media" \
        -e WEB_VANILLA_PLAY="$vanilla_play" -e WEB_VANILLA_MEDIA="$vanilla_media" -e VANILLA_PLAYER="$player" \
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
            mkdir -p /usr/share/nginx/vanilla/play /usr/share/nginx/vanilla/media/play/v2/client /usr/share/nginx/vanilla/media/play/web_service
            echo vanilla > /usr/share/nginx/vanilla/media/play/v2/client/club_penguin.swf
            dockerize -template /t/sites/vanilla.conf.template:/etc/nginx/conf.d/vanilla.conf
            dockerize -template /t/vanilla-media/media/play/web_service/environment_data.xml.template:/usr/share/nginx/vanilla/media/play/web_service/environment_data.xml
            for locale in en es fr pt; do
                source=/t/vanilla-media/play/$locale/index.html.template
                [ "$locale" != en ] || source=/t/vanilla-media/play/index.html.template
                mkdir -p /usr/share/nginx/vanilla/play/$locale
                dockerize -template "$source:/usr/share/nginx/vanilla/play/$locale/index.html"
            done
            cp /usr/share/nginx/vanilla/play/en/index.html /usr/share/nginx/vanilla/play/index.html
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
            vplayhost=$(echo "$WEB_VANILLA_PLAY" | cut -d/ -f3)
            vmediahost=$(echo "$WEB_VANILLA_MEDIA" | cut -d/ -f3)
            vplaypath=$(echo "$WEB_VANILLA_PLAY" | cut -d/ -f4-)
            vmediapath=$(echo "$WEB_VANILLA_MEDIA" | cut -d/ -f4-)
            wget -qO /tmp/vanilla --header="Host: $vplayhost" "http://127.0.0.1/${vplaypath:+$vplaypath/}"
            if [ "$VANILLA_PLAYER" = flash ]; then ! grep -q /__wand/ruffle/vanilla.js /tmp/vanilla; else grep -q /__wand/ruffle/vanilla.js /tmp/vanilla; fi
            wget -qO- --header="Host: $vmediahost" "http://127.0.0.1/${vmediapath:+$vmediapath/}play/v2/client/club_penguin.swf" | grep -q vanilla
            wget -qO- --header="Host: $vplayhost" http://127.0.0.1/__wand/ruffle/vanilla.js > /dev/null
            wasm=$(basename "$(find /opt/wand/ruffle -name "*.wasm" | head -1)")
            wget -SO /dev/null --header="Host: $playhost" "http://127.0.0.1/__wand/ruffle/$wasm" 2>&1 | grep -qi "Content-Type: application/wasm"
        '
done
