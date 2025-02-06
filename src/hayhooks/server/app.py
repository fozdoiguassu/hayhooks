from os import PathLike
from typing import Union
from fastapi import FastAPI
from pathlib import Path
from hayhooks.server.utils.deploy_utils import (
    deploy_pipeline_def,
    PipelineDefinition,
    deploy_pipeline_files,
    read_pipeline_files_from_dir,
)
from hayhooks.server.routers import status_router, draw_router, deploy_router, undeploy_router, openai_router
from hayhooks.settings import settings
from hayhooks.server.logger import log


def deploy_yaml_pipeline(app: FastAPI, pipeline_file_path: Path) -> dict:
    """
    Deploy a pipeline from a YAML file.

    Args:
        app: FastAPI application instance
        pipeline_file_path: Path to the YAML pipeline definition

    Returns:
        dict: Deployment result containing pipeline name
    """
    name = pipeline_file_path.stem
    with open(pipeline_file_path, "r") as pipeline_file:
        source_code = pipeline_file.read()

    pipeline_definition = PipelineDefinition(name=name, source_code=source_code)
    deployed_pipeline = deploy_pipeline_def(app, pipeline_definition)
    log.info(f"Deployed pipeline from yaml: {deployed_pipeline['name']}")
    return deployed_pipeline


def deploy_files_pipeline(app: FastAPI, pipeline_dir: Path) -> dict:
    """
    Deploy a pipeline from a directory containing multiple files.

    Args:
        app: FastAPI application instance
        pipeline_dir: Path to the pipeline directory

    Returns:
        dict: Deployment result containing pipeline name
    """
    name = pipeline_dir.name
    files = read_pipeline_files_from_dir(pipeline_dir)

    if files:
        deployed_pipeline = deploy_pipeline_files(app, name, files)
        log.info(f"Deployed pipeline from dir: {deployed_pipeline['name']}")
        return deployed_pipeline
    return {"name": name}


def create_pipeline_dir(pipelines_dir: Union[PathLike, str]):
    """
    Create a directory for pipelines if it doesn't exist.

    If the directory doesn't exist, it will be created.
    If the directory exists but is not a directory, an error will be raised.

    Args:
        pipelines_dir: Path to the pipelines directory

    Returns:
        str: Path to the pipelines directory
    """
    pipelines_dir = Path(pipelines_dir)

    if not pipelines_dir.exists():
        log.info(f"Creating pipelines dir: {pipelines_dir}")
        pipelines_dir.mkdir(parents=True, exist_ok=True)

    if not pipelines_dir.is_dir():
        raise ValueError(f"pipelines_dir '{pipelines_dir}' exists but is not a directory")

    return str(pipelines_dir)


def create_app() -> FastAPI:
    """
    Create and configure a FastAPI application.

    This function initializes a FastAPI application with the following features:
    - Configures root path from settings if provided
    - Includes all router endpoints (status, draw, deploy, undeploy)
    - Auto-deploys pipelines from the configured pipelines directory:
        - YAML pipeline definitions (*.yml, *.yaml)
        - Pipeline directories containing multiple files

    Returns:
        FastAPI: Configured FastAPI application instance
    """
    if root_path := settings.root_path:
        app = FastAPI(root_path=root_path)
    else:
        app = FastAPI()

    # Include all routers
    app.include_router(status_router)
    app.include_router(draw_router)
    app.include_router(deploy_router)
    app.include_router(undeploy_router)
    app.include_router(openai_router)

    # Deploy all pipelines in the pipelines directory
    pipelines_dir = create_pipeline_dir(settings.pipelines_dir)

    if pipelines_dir:
        log.info(f"Pipelines dir set to: {pipelines_dir}")
        pipelines_path = Path(pipelines_dir)

        yaml_files = list(pipelines_path.glob("*.y*ml"))
        pipeline_dirs = [d for d in pipelines_path.iterdir() if d.is_dir()]

        if yaml_files:
            log.info(f"Deploying {len(yaml_files)} pipeline(s) from YAML files")
            for pipeline_file_path in yaml_files:
                try:
                    deploy_yaml_pipeline(app, pipeline_file_path)
                except Exception as e:
                    log.warning(f"Skipping pipeline file {pipeline_file_path}: {str(e)}")
                    continue

        if pipeline_dirs:
            log.info(f"Deploying {len(pipeline_dirs)} pipeline(s) from directories")
            for pipeline_dir in pipeline_dirs:
                try:
                    deploy_files_pipeline(app, pipeline_dir)
                except Exception as e:
                    log.warning(f"Skipping pipeline directory {pipeline_dir}: {str(e)}")
                    continue

    return app
