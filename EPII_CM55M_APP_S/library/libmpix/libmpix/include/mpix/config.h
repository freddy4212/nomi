/**
 * SPDX-License-Identifier: Apache-2.0
 * @internal
 * TODO better Kconfig integration
 * TODO better CMakeLists.txt integration for UNIX ports
 * @{
 */
#ifndef MPIX_CONFIG_H
#define MPIX_CONFIG_H

#include <stdbool.h>

#ifdef HAS_CONFIG_H
#include "config.h"
#endif

#ifndef CONFIG_MPIX_LOG_LEVEL
#define CONFIG_MPIX_LOG_LEVEL 3
#endif

#endif /* @} */
