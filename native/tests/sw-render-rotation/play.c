/* 用不同颜色的象限核对旋转方向，并检查中心亮块随播放出现。 */
#define _POSIX_C_SOURCE 200809L
#include <mpv/client.h>
#include <mpv/render.h>

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

enum { WIDTH = 384, HEIGHT = 216 };
enum color { BLACK, RED, GREEN, BLUE, YELLOW, WHITE, UNKNOWN };

static _Alignas(64) uint8_t pixels[HEIGHT][WIDTH][4];

static enum color color_at(int x, int y)
{
    const uint8_t *rgb = pixels[y][x];
    int r = rgb[0], g = rgb[1], b = rgb[2];
    if (r < 30 && g < 30 && b < 30)
        return BLACK;
    if (r > 150 && g > 150 && b > 150)
        return WHITE;
    if (r > 140 && g > 140 && b < 65)
        return YELLOW;
    if (r > 135 && g < 70 && b < 70)
        return RED;
    if (g > 110 && r < 70 && b < 70)
        return GREEN;
    if (b > 135 && r < 70 && g < 70)
        return BLUE;
    return UNKNOWN;
}

static bool correct_orientation(int quarter_turns)
{
    /* MP4 显示矩阵的正角度为逆时针。测试样片的像素宽高比为 16:9。 */
    static const enum color expected[4][4] = {
        {RED, GREEN, BLUE, YELLOW},
        {GREEN, YELLOW, RED, BLUE},
        {YELLOW, BLUE, GREEN, RED},
        {BLUE, RED, YELLOW, GREEN},
    };
    int dx = (quarter_turns % 2 ? HEIGHT * 9 / 16 : WIDTH) / 4;
    return color_at(WIDTH / 2 - dx, HEIGHT / 4) == expected[quarter_turns][0]
        && color_at(WIDTH / 2 + dx, HEIGHT / 4) == expected[quarter_turns][1]
        && color_at(WIDTH / 2 - dx, HEIGHT * 3 / 4) == expected[quarter_turns][2]
        && color_at(WIDTH / 2 + dx, HEIGHT * 3 / 4) == expected[quarter_turns][3]
        && (quarter_turns % 2 == 0 || color_at(8, HEIGHT / 2) == BLACK);
}

static void require_mpv(int status, const char *action)
{
    if (status < 0) {
        fprintf(stderr, "%s: %s\n", action, mpv_error_string(status));
        exit(EXIT_FAILURE);
    }
}

static double monotonic_seconds(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec / 1e9;
}

int main(int argc, char **argv)
{
    if (argc != 3 || argv[2][0] < '0' || argv[2][0] > '3' || argv[2][1]) {
        fprintf(stderr, "usage: %s MP4 QUARTER_TURNS_0_TO_3\n", argv[0]);
        return EXIT_FAILURE;
    }
    int quarter_turns = argv[2][0] - '0';

    mpv_handle *mpv = mpv_create();
    if (!mpv)
        return EXIT_FAILURE;
    require_mpv(mpv_set_option_string(mpv, "config", "no"), "config");
    require_mpv(mpv_set_option_string(mpv, "vo", "libmpv"), "vo");
    require_mpv(mpv_set_option_string(mpv, "audio", "no"), "audio");
    require_mpv(mpv_set_option_string(mpv, "hwdec", "no"), "hwdec");
    require_mpv(mpv_set_option_string(mpv, "osd-level", "0"), "osd");
    require_mpv(mpv_initialize(mpv), "initialize");

    mpv_render_context *render = NULL;
    mpv_render_param api[] = {
        {MPV_RENDER_PARAM_API_TYPE, MPV_RENDER_API_TYPE_SW},
        {MPV_RENDER_PARAM_INVALID, NULL},
    };
    require_mpv(mpv_render_context_create(&render, mpv, api), "SW context");

    mpv_render_param invalid_target[] = {{MPV_RENDER_PARAM_INVALID, NULL}};
    if (mpv_render_context_render(render, invalid_target) != MPV_ERROR_INVALID_PARAMETER) {
        fputs("missing software target was accepted\n", stderr);
        return EXIT_FAILURE;
    }

    int size[] = {WIDTH, HEIGHT};
    size_t stride = sizeof pixels[0];
    mpv_render_param target[] = {
        {MPV_RENDER_PARAM_SW_SIZE, size},
        {MPV_RENDER_PARAM_SW_FORMAT, "rgb0"},
        {MPV_RENDER_PARAM_SW_STRIDE, &stride},
        {MPV_RENDER_PARAM_SW_POINTER, pixels},
        {MPV_RENDER_PARAM_INVALID, NULL},
    };
    const char *load[] = {"loadfile", argv[1], NULL};
    require_mpv(mpv_command_async(mpv, 1, load), "loadfile");
    bool visible = false, moving = false;
    const double deadline = monotonic_seconds() + 8;
    while (!moving && monotonic_seconds() < deadline) {
        for (mpv_event *event; (event = mpv_wait_event(mpv, 0))->event_id;) {
            if (event->event_id == MPV_EVENT_COMMAND_REPLY)
                require_mpv(event->error, "loadfile reply");
            if (event->event_id == MPV_EVENT_END_FILE) {
                const mpv_event_end_file *end = event->data;
                require_mpv(end->error, "end file");
            }
        }
        if (mpv_render_context_update(render) & MPV_RENDER_UPDATE_FRAME) {
            require_mpv(mpv_render_context_render(render, target), "render");
            if (color_at(WIDTH / 2 - size[0] / 10, HEIGHT / 4) != BLACK) {
                if (!correct_orientation(quarter_turns)) {
                    fprintf(stderr, "%d°: visible frame has incorrect orientation\n",
                            90 * quarter_turns);
                    break;
                }
                bool marker = color_at(WIDTH / 2, HEIGHT / 2) == WHITE;
                moving = visible && marker;
                visible |= !marker;
            }
        }
        nanosleep(&(struct timespec){.tv_nsec = 5000000}, NULL);
    }

    mpv_render_context_free(render);
    mpv_terminate_destroy(mpv);
    printf("%d°: first frame=%d, later frame=%d\n", 90 * quarter_turns, visible, moving);
    return moving ? EXIT_SUCCESS : EXIT_FAILURE;
}
