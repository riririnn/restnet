#include "t_mode_handler.h"

int main(int argc, char* argv[])
{
    transformer::ModeHandler mode_handler;
    mode_handler.run(argc, argv);
    return 0;
}
